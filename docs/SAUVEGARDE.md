# Sauvegarde et restauration de la base Neon

## Ce qui tourne

Le workflow **Sauvegarde de la base** (`.github/workflows/sauvegarde-base.yml`) tourne chaque nuit
à 3 h 15 (heure de Yaoundé) :

1. `pg_dump` de la base Neon (format custom, compressé), avec l'image `postgres:<N>-alpine` de la
   version du serveur. L'hôte « -pooler » de Neon est remplacé par l'hôte direct.
2. Chiffrement AES-256 (gpg, phrase secrète `BACKUP_PASSPHRASE`).
3. **Restauration d'essai** du fichier chiffré dans un PostgreSQL jetable, puis comparaison des
   nombres de lignes avec la base réelle. Une sauvegarde qui ne se restaure pas fait échouer le
   workflow.
4. Envoi du fichier chiffré comme artefact `sauvegarde-neon-<run>`, gardé **90 jours** (le maximum
   de GitHub pour les artefacts).
5. Facultatif : le 1er du mois, copie du même fichier comme release d'un dépôt **privé**, gardée sans
   limite de durée.

En cas d'échec, un ticket « Sauvegarde de la base en échec » est ouvert (ou commenté) dans ce dépôt
et assigné au propriétaire : GitHub l'envoie par e-mail.

## Limites à connaître

- **Le dépôt est public** : n'importe quel compte GitHub peut télécharger les artefacts. Ils ne se
  lisent qu'avec `BACKUP_PASSPHRASE`, qui doit être longue (20 caractères minimum, le script refuse
  moins) et rangée dans le gestionnaire de mots de passe. **Sans elle, les sauvegardes sont
  inutilisables** ; si elle fuit, il faut la changer (les anciennes sauvegardes restent lisibles
  avec l'ancienne).
- Tout reste chez GitHub (artefacts et dépôt privé) : un compte GitHub piraté ou supprimé emporte
  les sauvegardes. D'où la 2FA, et l'intérêt de télécharger de temps en temps une copie ailleurs
  (Google Drive de la librairie, par exemple).
- GitHub **désactive les workflows planifiés d'un dépôt public après 60 jours sans commit**. Il
  prévient par e-mail ; il suffit alors de cliquer « Enable workflow » dans l'onglet Actions.
- Une sauvegarde par nuit : jusqu'à 24 h de commandes peuvent manquer après une restauration. Pour
  une erreur récente, la restauration instantanée de Neon (« Restore », quelques heures d'historique
  sur l'offre gratuite) est plus fine ; elle ne remplace pas une sauvegarde, puisqu'elle disparaît
  avec le projet Neon.
- Les secrets d'Actions sont lisibles par toute personne qui peut pousser un workflow sur `main`
  (Ghislain compris) : c'est une raison de plus pour protéger `main`.

## Mise en place (une fois)

Dans ce dépôt : **Settings → Secrets and variables → Actions → New repository secret**.

| Secret | Valeur |
|---|---|
| `DATABASE_URL` | La même URL que dans Render (groupe `CommandeLivraisonLipaCentreGroup`). Toutes les formes sont acceptées (`postgres://`, `postgresql+asyncpg://`, hôte `-pooler`). |
| `BACKUP_PASSPHRASE` | Une phrase secrète d'au moins 20 caractères, générée par le gestionnaire de mots de passe et enregistrée **avant** d'être collée ici. |

Puis **Actions → Sauvegarde de la base → Run workflow** pour lancer une première sauvegarde et
vérifier qu'elle passe au vert.

### Copie mensuelle dans un dépôt privé (recommandée)

1. Créer un dépôt **privé** vide, par exemple `leudjeu-hub/lipacentre-sauvegardes`.
2. Créer un jeton : **GitHub → Settings → Developer settings → Personal access tokens →
   Fine-grained tokens → Generate new token**. Repository access : *Only select repositories* →
   ce dépôt privé seulement. Permissions : *Contents : Read and write*. Noter sa date d'expiration
   dans l'agenda : à l'expiration, la copie mensuelle échoue (ticket d'alerte).
3. Dans le dépôt backend : secret `BACKUP_REPO_TOKEN` = ce jeton, et onglet **Variables** →
   `BACKUP_REPO` = `leudjeu-hub/lipacentre-sauvegardes`.

## Restaurer

### Choisir la base cible

Ne pas restaurer directement dans la production sans l'avoir décidé. Le plus sûr :

1. Neon → projet → **Branches → Create branch** (depuis `main`, nom `restauration`), puis copier
   la *connection string* de cette branche.
2. Restaurer dans cette branche (ci-dessous) et vérifier les données (commandes, produits, comptes).
3. Si tout est bon : soit mettre cette URL dans `DATABASE_URL` du groupe Render et redéployer, soit
   restaurer une seconde fois en visant la base principale.

### Lancer la restauration

1. Secret `RESTORE_DATABASE_URL` = l'URL de la base cible (le mettre au moment de la restauration,
   et le supprimer après).
2. **Actions → Restaurer une sauvegarde → Run workflow** : laisser *run_id* vide pour la dernière
   sauvegarde réussie (ou mettre le numéro d'une exécution de « Sauvegarde de la base », visible
   dans son URL `/actions/runs/<numéro>`), écrire `RESTAURER` dans *confirmation*.
3. Le journal se termine par le nombre de lignes de chaque table restaurée.

Les tables de la base cible sont remplacées en une seule transaction : en cas d'erreur, rien n'est
modifié. Une base dont le schéma diffère (autres colonnes) peut refuser la restauration : viser
alors une base vide ou une branche Neon neuve.

### À la main (sans GitHub Actions)

Avec Docker et gpg sur un ordinateur (fichier `.dump.gpg` téléchargé depuis l'artefact, puis
dézippé) :

```bash
export BACKUP_PASSPHRASE='…'
export RESTORE_DATABASE_URL='postgresql://…'
scripts/sauvegarde.sh restore neon-AAAA-MM-JJ-pg17.dump.gpg
# ou, sans rien restaurer, vérifier qu'une sauvegarde est lisible :
scripts/sauvegarde.sh verify neon-AAAA-MM-JJ-pg17.dump.gpg
```

Sans le script : `gpg --decrypt fichier.dump.gpg > base.dump`, puis
`pg_restore --no-owner --no-privileges --clean --if-exists -d "$URL" base.dump` avec un
`pg_restore` de la même version majeure que dans le nom du fichier (`-pg17`).

## Quand la sauvegarde échoue

Ouvrir l'exécution liée dans le ticket et lire la première ligne rouge :

- « Connexion à la base impossible » : `DATABASE_URL` a changé (mot de passe Neon réinitialisé ?)
  → mettre à jour le secret avec l'URL de Render.
- « Déchiffrement impossible » : `BACKUP_PASSPHRASE` a été modifiée entre le chiffrement et le test.
- « Aucun produit » / « alembic_version manquante » : la base sauvegardée est vide ou cassée → ne
  surtout pas restaurer par-dessus ; comparer avec les sauvegardes précédentes.
- Erreur dans « Copie mensuelle » : jeton `BACKUP_REPO_TOKEN` expiré → en générer un nouveau.

Fermer le ticket quand une exécution repasse au vert.
