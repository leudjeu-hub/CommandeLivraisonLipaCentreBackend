#!/usr/bin/env bash
# Encrypted backups of the Neon database (see docs/SAUVEGARDE.md).
#
#   scripts/sauvegarde.sh dump    <dir>   DATABASE_URL -> <dir>/neon-<date>-pg<N>.dump.gpg
#   scripts/sauvegarde.sh verify  <file>  restores <file> into a throwaway PostgreSQL and compares
#                                         its row counts with DATABASE_URL (if set)
#   scripts/sauvegarde.sh restore <file>  restores <file> into RESTORE_DATABASE_URL (replaces its tables)
#
# BACKUP_PASSPHRASE encrypts/decrypts (gpg, AES-256). The PostgreSQL tools run in the official
# postgres:<N>-alpine image of the server's major version: pg_dump must not be older than the
# server, and pg_restore of another major version can emit settings the server rejects.
# Needs docker and gpg (both on GitHub's ubuntu runners).
set -euo pipefail

die() { echo "::error::$*" >&2; exit 1; }

# Accept the URL as Render/the app has it: postgres://, postgresql+asyncpg://, ssl=require.
# Neon's pooled host (-pooler) goes through PgBouncer, which pg_dump should not use: take the
# direct host instead.
libpq_url() {
  local url="$1"
  url="${url/#postgres:\/\//postgresql://}"
  url="${url/#postgresql+asyncpg:\/\//postgresql://}"
  url="${url//\?ssl=/?sslmode=}"
  url="${url//&ssl=/&sslmode=}"
  url="${url/-pooler./.}"
  printf '%s' "$url"
}

# pg_run <major> <url> <shell command using "$PGURL"> [docker args...]
pg_run() {
  local major="$1" url="$2" cmd="$3"
  shift 3
  docker run --rm -i --network host -e PGURL="$url" "$@" "postgres:${major}-alpine" sh -c "$cmd"
}

server_major() {
  local num
  num=$(pg_run 17 "$1" 'psql "$PGURL" -XtAc "show server_version_num"') \
    || die "Connexion à la base impossible (URL ou mot de passe ?)"
  echo $((num / 10000))
}

# "table=rows ..." for every table of the public schema
ROW_COUNTS_SQL="select string_agg(table_name || '=' || (xpath('/row/c/text()', query_to_xml(
  format('select count(*) as c from public.%I', table_name), false, true, '')))[1]::text, ' '
  order by table_name) from information_schema.tables
  where table_schema = 'public' and table_type = 'BASE TABLE'"

row_counts() {
  pg_run "$1" "$2" "psql \"\$PGURL\" -XtAc \"$ROW_COUNTS_SQL\""
}

need_passphrase() {
  [ -n "${BACKUP_PASSPHRASE:-}" ] || die "Le secret BACKUP_PASSPHRASE est vide"
  [ "${#BACKUP_PASSPHRASE}" -ge 20 ] || die "BACKUP_PASSPHRASE doit faire au moins 20 caractères"
}

decrypt() {
  printf '%s' "$BACKUP_PASSPHRASE" | gpg --batch --quiet --pinentry-mode loopback \
    --passphrase-fd 0 --decrypt --output "$2" "$1" || die "Déchiffrement impossible (mauvaise phrase secrète ?)"
}

major_of() {
  local major
  major=$(basename "$1" | sed -n 's/.*-pg\([0-9][0-9]*\)\.dump\.gpg$/\1/p')
  [ -n "$major" ] || die "Nom de fichier inattendu : $1 (attendu neon-<date>-pg<N>.dump.gpg)"
  echo "$major"
}

cmd_dump() {
  local dir="$1" url major work out
  [ -n "${DATABASE_URL:-}" ] || die "Le secret DATABASE_URL est vide"
  need_passphrase
  url=$(libpq_url "$DATABASE_URL")
  major=$(server_major "$url")
  echo "Serveur PostgreSQL $major"
  mkdir -p "$dir"
  work=$(mktemp -d)
  chmod 777 "$work"
  pg_run "$major" "$url" 'pg_dump "$PGURL" --format=custom --compress=9 --no-owner --no-privileges --file=/work/base.dump' \
    -v "$work:/work"
  [ -s "$work/base.dump" ] || die "pg_dump n'a rien produit"
  pg_run "$major" "" 'pg_restore --list /work/base.dump' -v "$work:/work" | grep -q 'TABLE DATA public orders' \
    || die "La sauvegarde ne contient pas la table orders"
  out="$dir/neon-$(date -u +%Y-%m-%d)-pg${major}.dump.gpg"
  printf '%s' "$BACKUP_PASSPHRASE" | gpg --batch --yes --quiet --pinentry-mode loopback \
    --passphrase-fd 0 --symmetric --cipher-algo AES256 --output "$out" "$work/base.dump"
  rm -rf "$work"
  echo "Sauvegarde chiffrée : $out ($(du -h "$out" | cut -f1))"
  if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "file=$out" >>"$GITHUB_OUTPUT"; fi
}

cmd_verify() {
  local file="$1" major work name expected actual
  need_passphrase
  major=$(major_of "$file")
  work=$(mktemp -d)
  chmod 777 "$work"
  decrypt "$file" "$work/base.dump"
  chmod 644 "$work/base.dump"
  name="restore-test-$$"
  docker run -d --rm --name "$name" -e POSTGRES_PASSWORD=test -p 127.0.0.1:55432:5432 \
    "postgres:${major}-alpine" >/dev/null
  trap 'docker stop '"$name"' >/dev/null 2>&1 || true; rm -rf '"$work" EXIT
  local target="postgresql://postgres:test@127.0.0.1:55432/postgres"
  for _ in $(seq 60); do
    pg_run "$major" "$target" 'psql "$PGURL" -XtAc "select 1"' >/dev/null 2>&1 && break
    sleep 1
  done
  pg_run "$major" "$target" 'pg_restore --dbname="$PGURL" --no-owner --no-privileges --exit-on-error /work/base.dump' \
    -v "$work:/work"
  actual=$(row_counts "$major" "$target")
  echo "Restaurée : $actual"
  echo "$actual" | grep -q 'alembic_version=1' || die "alembic_version manquante dans la copie restaurée"
  echo "$actual" | grep -Eq 'products=[1-9]' || die "Aucun produit dans la copie restaurée"
  if [ -n "${DATABASE_URL:-}" ]; then
    expected=$(row_counts "$major" "$(libpq_url "$DATABASE_URL")")
    echo "Base actuelle : $expected"
    # Orders placed between the dump and now can differ: only a warning
    [ "$expected" = "$actual" ] || echo "::warning::Nombres de lignes différents de la base actuelle (commandes passées depuis la sauvegarde ?)"
  fi
  echo "Restauration testée : OK"
}

cmd_restore() {
  local file="$1" major work url
  [ -n "${RESTORE_DATABASE_URL:-}" ] || die "Le secret RESTORE_DATABASE_URL est vide"
  need_passphrase
  major=$(major_of "$file")
  url=$(libpq_url "$RESTORE_DATABASE_URL")
  work=$(mktemp -d)
  chmod 777 "$work"
  trap 'rm -rf '"$work" EXIT
  decrypt "$file" "$work/base.dump"
  chmod 644 "$work/base.dump"
  pg_run "$major" "$url" 'pg_restore --dbname="$PGURL" --clean --if-exists --no-owner --no-privileges --single-transaction --exit-on-error /work/base.dump' \
    -v "$work:/work"
  echo "Restaurée dans la base cible : $(row_counts "$major" "$url")"
}

case "${1:-}" in
  dump) cmd_dump "${2:?dossier}" ;;
  verify) cmd_verify "${2:?fichier}" ;;
  restore) cmd_restore "${2:?fichier}" ;;
  *) die "usage: $0 dump <dossier> | verify <fichier> | restore <fichier>" ;;
esac
