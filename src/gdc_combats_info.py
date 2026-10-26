import os
import sys
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
import pandas as pd
import requests

def requete_API(cle_API, identifiant, option=None, session=None):
    """
    Fonction pour envoyer une requête à l'API de Clash Royale afin de récupérer des informations disponibles sur un clan.

    Paramètres :
    cle_API (str) : Clé d'accès à l'API de Clash Royale.
    identifiant (str) : Identifiant Supercell.
    option (str, optionnel) : Option pour spécifier le type d'information désirée
                                (None, "members", "riverracelog", "currentriverrace").
    session (requests.Session, optionnel) : Session HTTP réutilisable pour de meilleures performances.

    Valeur de retour :
    dict or None : Dictionnaire Python contenant la réponse de l'API, ou None en cas d'erreur.
    """
    try:
        # Nettoyage et validation de l'identifiant
        identifiant = identifiant.strip('#')
        if not (6 <= len(identifiant) <= 10) or not identifiant.isalnum():
            print(f"\nL'identifiant est invalide. Il doit comporter entre 6 et 10 caractères alphanumériques.")
            return None

        # Configuration des URLs et des routes
        url_source = "https://proxy.royaleapi.dev/v1"
        routes = {
            "clan: info": f"{url_source}/clans/%23{identifiant}",
            "clan: membres": f"{url_source}/clans/%23{identifiant}/members",
            "guerre: actuelle": f"{url_source}/clans/%23{identifiant}/currentriverrace",
            "guerre: historique": f"{url_source}/clans/%23{identifiant}/riverracelog",
            "joueur: info": f"{url_source}/players/%23{identifiant}",
            "joueur: combats": f"{url_source}/players/%23{identifiant}/battlelog"
        }

        if option not in routes:
            print(f"\nL'option '{option}' n'est pas valide.")
            print(f"\nOptions disponibles : {list(routes.keys())[1:]}")
            return None

        rep_cible = routes[option]

        # Préparation de la requête
        en_tetes = {
            "Authorization": f"Bearer {cle_API}",
            "Accept": "application/json",
        }

        # Utilisation d'une session existante ou création d'une session temporaire
        client = session if session else requests

        # Exécution de la requête
        reponse = client.get(rep_cible, headers=en_tetes, timeout=10)

        # Lève automatiquement une exception pour les codes 4xx/5xx
        reponse.raise_for_status()
#        print(f"Connexion réussie à l'API de Clash Royale via le lien\n {rep_cible}")
        return reponse.json()

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "inconnu"
        if status == 403:
            print(f"\nÉchec d'authentification (403). Vérifiez votre clé API et votre adresse IP.")
            return None
        elif status == 400:
            print(f"\nRequête incorrecte (400) : {e.response.text if e.response else ''}")
            return None
        elif status == 404:
            print(f"\nRessource introuvable (404) : Le clan ou le joueur '{identifiant}' est introuvable sur l'API.")
            return None
        else:
            print(f"\nProblème API (Code {status}) : {e.response.text if e.response else e}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"\nErreur réseau ou timeout : {e}")
        return None

    except Exception as e:
        print(f"\nUne erreur inattendue est survenue : {e}")
        return None

def lecture_fichier_CSV(fichier):
    """
    Cette fonction lit un fichier CSV et retourne un DataFrame Pandas.

    Args:
        fichier (str): Le chemin du fichier CSV à lire.

    Returns:
        pandas.DataFrame: Un DataFrame contenant les données du fichier CSV, ou None en cas d'erreur.
    """
    try:
        df = pd.read_csv(fichier)
        print(f"\nLe fichier {fichier} a été lu avec succès.")
        return df

    except FileNotFoundError:
        print(f"\nErreur: Le fichier {fichier} n'a pas été trouvé. Veuillez vérifier le chemin du fichier.")
        return None

    except pd.errors.EmptyDataError:
        print(f"\nErreur: Le fichier {fichier} est vide ou ne contient pas de données valides.")
        return None

    except pd.errors.ParserError:
        print(f"\nErreur: Impossible d'analyser le fichier {fichier}. Veuillez vous assurer qu'il s'agit d'un fichier CSV valide et que le format est correct.")
        return None

    except UnicodeDecodeError:
        print(f"\nErreur: Impossible de décoder le fichier {fichier}. Veuillez vous assurer qu'il est encodé en UTF-8 ou spécifiez l'encodage approprié.")
        return None

    except Exception as e:
        print(f"\nUne erreur inattendue s'est produite lors de la lecture du fichier {fichier}: {e}")
        return None

def sauvegarder_dataframe_csv(dataframe, nom_fichier):
    """Sauvegarder un DataFrame de manière sécurisée en passant par un fichier temporaire
    pour éviter de corrompre ou d'effacer le fichier original si le script plante.

    Arguments :
    dataframe (DataFrame) : Le DataFrame à sauvegarder.
    nom_fichier (Path) : Le chemin final du fichier CSV où sauvegarder le DataFrame.
    """
    if dataframe is None or dataframe.empty:
        print(f"\nSécurité sauvegarde : Le DataFrame est vide ou invalide.\n Sauvegarde annulée.")
        return

    # S'assurer que les colonnes vitales n'ont pas disparu par erreur
    if 'supercell_ID' not in dataframe.columns or 'pseudonyme' not in dataframe.columns:
        print(f"\nSécurité sauvegarde : Colonnes critiques manquantes. \n Sauvegarde annulée.")
        return

    nom_fichier = Path(nom_fichier)
    fichier_temp = nom_fichier.with_suffix('.csv.tmp')

    try:
        # Écrire dans le fichier temporaire d'abord
        dataframe.to_csv(fichier_temp, index=False)

        # Remplacer atomiquement le fichier original par le fichier temporaire valide
        if os.path.exists(fichier_temp):
            if os.path.exists(nom_fichier):
                os.remove(nom_fichier)  # Requis sur Windows avant os.rename
            os.rename(fichier_temp, nom_fichier)
            print(f"\nLe DataFrame a été sauvegardé dans\n {nom_fichier}.")
    except (IOError, OSError) as e:
        print(f"\nUne erreur s'est produite lors de la sauvegarde sécurisée : {e}")
        if os.path.exists(fichier_temp):
            try:
                os.remove(fichier_temp)
            except Exception:
                pass

def analyse_gdc(ma_cle, ma_session, saison, semaine, joueurTag, clanTag, tempsDebut, tempsFin):
    """
    Analyse les combats de guerre (GDC) d'un joueur effectués au cours d'une période spécifiée.

    Args:
        ma_cle (str): Clé d'accès pour l'API de Clash Royale
        saison (int): Saison de la guerre
        semaine (int): Semaine de la saison en cours
        joueurTag (str): Identifiant Supercell unique du joueur.
        clanTag (str): Identifiant Supercell unique du clan.
        tempsDebut (datetime): Le temps à partir duquel les combats de guerre doivent être inclus dans l'analyse.
        tempsFin (datetime): Le temps limit à inclure dans l'analyse

   Returns:
        list: Une liste de tuples contenant les détails de chaque combat analysé.
    """

    # nonlocal saison, semaine

    # Obtenir l'historique des combats du joueur
    joueurCombats = requete_API(ma_cle, joueurTag, 'joueur: combats', session=ma_session)

    if not joueurCombats:
        print("Aucune donnée disponible")
        return []
    
    resultats = []

    for combat in joueurCombats:
        team = combat.get('team', [{}])
        opponent = combat.get('opponent', [{}])
        
        # Sécurité pour s'assurer que les données du clan existent
        if not team or not team[0].get('clan'):
            continue

        # Filtrer par période temporelle et par tag de clan correspondant
        tempsCombat = parse_cr_timestamp(combat.get('battleTime', ''))
        if (tempsCombat > tempsDebut) and (tempsCombat < tempsFin) and (team[0]['clan'].get('tag') == clanTag):
            typeCombat = combat.get('type')
            mode = combat['gameMode']['name']
            nombreVictoire = 0
            nombreDefaite  = 0

            # Combat de guerre singulier (PvP)
            if typeCombat == 'riverRacePvP':
                participantCouronnes = team[0].get('crowns', 0)
                opponentCouronnes = opponent[0].get('crowns', 0)
                victoire = int(participantCouronnes > opponentCouronnes)
                nombreVictoire = int(participantCouronnes > opponentCouronnes)
                nombreDefaite = 1 - nombreVictoire
                
            # Duel en colisée
            elif typeCombat in ['riverRaceDuel', 'riverRaceDuelColosseum']:
                # Extraire les couronnes remportées pour chacune des manches du duel
                participantCouronnes = [j.get('crowns', 0) for i in team for j in i.get('rounds', [])]
                adversaireCouronnes = [j.get('crowns', 0) for i in opponent for j in i.get('rounds', [])]

                # Déterminer si le participant à gagner (victoire=1) ou perdu (victoire=0) le duel
                victoire = 0
                if len(participantCouronnes) == len(adversaireCouronnes) and participantCouronnes:
                    nombreVictoire = sum(p > a for p, a in zip(participantCouronnes, adversaireCouronnes))
                    nombreDefaite = len(participantCouronnes) - nombreVictoire
                    victoire = int(nombreVictoire > nombreDefaite)
                else:
                    print(f"\nQuelque chose ne fonctionne pas avec l'analyse d'un duel!")

                # Déterminer le nombre de couronnes remportées au total
                participantCouronnes = team[0].get('crowns', 0)
                opponentCouronnes = opponent[0].get('crowns', 0)
            else:
                continue
            
            # Stocker les résultats pour ce combat
            resultats.append((
                combat['battleTime'],
                saison,
                semaine,
                team[0].get('tag', ''), 
                team[0].get('name', ''),  
                typeCombat,
                mode,
                victoire,
                nombreVictoire,
                nombreDefaite
            ))
            
    return resultats

def parse_cr_timestamp(timestamp_str):
    """Convertit le format de date Clash Royale (ex: 20261001T143500.000Z) en objet datetime."""
    return datetime.strptime(timestamp_str, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=timezone.utc)
    
if 'google.colab' in sys.modules:
    from google.colab import drive

    # Monte le Drive uniquement s'il n'est pas déjà monté
    if not os.path.exists('/content/drive/MyDrive'):
        drive.mount('/content/drive')
    else:
        print(f"\nGoogle Drive est déjà monté.")

    dossier_fichiers = Path("/content/drive/MyDrive/Clash_Royale")
    print(f"\nMode détecté : Google Colab")
else:
    # Répertoire de base sur l'ordinateur
    dossier_fichiers = Path("C:/Users/schretien/Desktop/Clash_Royale")
    print(f"\nMode détecté : Local (Ordinateur)")

print(f"Dossier de travail configuré : {dossier_fichiers}")

# Définir la clé API
cle_API = dossier_fichiers / "CR_API_proxy.txt"

# Vérifier que le fichier existe
if not os.path.exists(cle_API):
    raise FileNotFoundError(
        f"Error: Le fichier '{cle_API}' contenant la clé API n'existe pas à l'endroit attendu.")

with open(cle_API, "r") as file:
    ma_cle = file.read().rstrip("\n")

# Définir l'identifiant Supercell du clan (avec ou sans le #)
clanTag = '#LURGRP' # Lausannegeles

# Déterminer la date du jeudi le plus récent
aujourdhui = date.today()
jour_cible = 3 # jeudi
jours_ecoules = (aujourdhui.weekday() - jour_cible) % 7
dernier_jeudi = aujourdhui - timedelta(days=jours_ecoules)

# Définir les temps du début et de fin de la guerre active
tempsDebut = datetime(dernier_jeudi.year, dernier_jeudi.month, dernier_jeudi.day, 10, 0, 0, tzinfo=timezone.utc)
tempsFin   = tempsDebut + timedelta(days=4, minutes=15)
print(f"Les combats de guerre effectués entre le {tempsDebut} et {tempsFin} seront conservés")

with requests.Session() as ma_session:
    # Obtenir les informations sur la guerre en cours
    guerreActuelle = requete_API(ma_cle, clanTag, 'guerre: actuelle', session=ma_session)
    nomClan = guerreActuelle['clan']['name']
    if guerreActuelle:
        print(f"\nLes infomations des membres du clan {nomClan} ont été récupérées")
    
    # Obtenir l'historiques des 10 dernières semaines de guerre
    guerreHistorique = requete_API(ma_cle, clanTag, 'guerre: historique', session=ma_session)
    if guerreHistorique:
        print(f"\nL'historique des guerre de clan a été récupérée")

    # Déterminer la saison et la semaine de la guerre en cours.
    #semaine = guerreActuelle['sectionIndex'] + 1 # Commence à zéro
    #saison = (guerreHistorique['items'][0]['seasonId'] + 1) if semaine == 1 else guerreHistorique['items'][0]['seasonId']
    if guerreActuelle['periodType'] == 'training':
        # Récupérer la semaine et la saison de la dernière semaine de guerre complétées
        semaine = guerreHistorique['items'][0]['sectionIndex'] + 1  # Commence à zéro
        saison  = guerreHistorique['items'][0]['seasonId']
    elif guerreActuelle['periodType'] in ['warDay', 'colosseum']:
        # Récupérer la semaine et la saison de la guerre en cours
        semaine = guerreActuelle['sectionIndex'] + 1 # Commence à zéro
        saison = (guerreHistorique['items'][0]['seasonId'] + 1) if semaine == 1 else guerreHistorique['items'][0]['seasonId']
    print(f"\nSaison {saison}, semaine {semaine}")

    # Extraire la liste des membres et leurs contributions
    participantTags  = [membre['tag'] for membre in guerreActuelle['clan']['participants']]
    participantNames = [membre['name'] for membre in guerreActuelle['clan']['participants']]

    # Extraire les combats de guerre de tous les membres ayant participé à la saison
    resultats = []
    for joueurTag in participantTags:
        resultats.extend(analyse_gdc(ma_cle, ma_session, saison, semaine, joueurTag, clanTag, tempsDebut, tempsFin))

# Créer un pandas Dataframe
nouveau_df = pd.DataFrame(resultats)
# Renommer les colonnes
nouveau_df.columns = ['temps', 'saison', 'semaine', 'supercell_ID', 'pseudonyme', 'typeCombat', 'mode', 'victoire', '#victoire', '#defaite']

# Définir le nom du fichier contenant l'historique de la semaine en cours
nom_fichier = dossier_fichiers / f"{nomClan}_gdc_{saison}_{semaine}.csv"

# Vérifier si le fichier existe
if os.path.exists(nom_fichier):
    # Lire le fichier contenant les résultats
    ancien_df = lecture_fichier_CSV(nom_fichier)

    # Combiner les nouveaux et les anciens résultats 
    df = pd.concat([ancien_df, nouveau_df])

    # Enlever les duplicats
    df.drop_duplicates(subset='temps', keep='first', inplace=True)
else:
    df = nouveau_df

# Sauvergarder le DataFrame
sauvegarder_dataframe_csv(df, nom_fichier)

# Définition des listes de modes
mode_duel = ["riverRaceDuel", "riverRaceDuelColosseum"]
mode_speciaux = ["TripleElixir_Ladder", "Touchdown_ClanWar", "Rage_Ladder", "RampUpElixir_Ladder"]

# Filtrage des combats
duel      = df[df["typeCombat"].isin(mode_duel)]
singulier = df[(df["typeCombat"] == "riverRacePvP") & (~df["mode"].isin(mode_speciaux))]
special   = df[(df["typeCombat"] == "riverRacePvP") & (df["mode"].isin(mode_speciaux))]

# Calculer les victoires et défaites pour chacun des modes.
categories = [
    ("duel", duel),
    ("1v1 régulier", singulier),
    ("1v1 spécial", special)
]

data = [
    {
        "mode": nom,
        "total": subset.shape[0],
        "victoire": subset["victoire"].sum(),
        "défaite": subset.shape[0] - subset["victoire"].sum(),
    }
    for nom, subset in categories
]

# Génération et affichage du DataFrame
analyse_combats_df = pd.DataFrame(data).set_index("mode")
print(f"\n\n{analyse_combats_df}")

victoires = df['#victoire'].sum()
defaites = df['#defaite'].sum()
print(f"\n\nNombre de victoires: {victoires}")
print(f"Nombre de défaites:  {defaites}")
print('-'*24)
print(f"Combats totals:      {victoires + defaites}")