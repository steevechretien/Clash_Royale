# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Compilation des statistiques de guerre de clan dans Clash Royale
# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# ===============================
# Chargement des modules employés
# ===============================

import pandas as pd
import numpy as np
import urllib.request, json

import os
import sys
import requests

import matplotlib.pyplot as plt
import seaborn as sns

from datetime import datetime, timezone, time, timedelta, date
from pathlib import Path

from typing import Dict, Any

# ============================
# Détection de l'environnement
# ============================

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

print(f"\nDossier de travail configuré : {dossier_fichiers}")

# ======================================================
# Lecture de la clé pour accéder à l'API de CLash Royale
# ======================================================

# Définir la clé API
cle_API = dossier_fichiers / "CR_API_proxy.txt"

# Vérifier que le fichier existe
if not cle_API.exists():
    raise FileNotFoundError(f"\nError: Le fichier '{cle_API}' contenant la clé API n'existe pas à l'endroit attendu.")

# Lire la clé
with open(cle_API, "r") as file:
    ma_cle = file.read().rstrip("\n")

# ==========================
# Definir quelques fonctions
# ==========================

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
        print(f"Le fichier {fichier} a été lu avec succès.")
        return df

    except FileNotFoundError:
        print(f"Erreur: Le fichier {fichier} n'a pas été trouvé. Veuillez vérifier le chemin du fichier.")
        return None

    except pd.errors.EmptyDataError:
        print(f"Erreur: Le fichier {fichier} est vide ou ne contient pas de données valides.")
        return None

    except pd.errors.ParserError:
        print(f"Erreur: Impossible d'analyser le fichier {fichier}. Veuillez vous assurer qu'il s'agit d'un fichier CSV valide et que le format est correct.")
        return None

    except UnicodeDecodeError:
        print(f"Erreur: Impossible de décoder le fichier {fichier}. Veuillez vous assurer qu'il est encodé en UTF-8 ou spécifiez l'encodage approprié.")
        return None

    except Exception as e:
        print(f"Une erreur inattendue s'est produite lors de la lecture du fichier {fichier}: {e}")
        return None

def sauvegarder_dataframe_csv(dataframe, nom_fichier):
    """Sauvegarder un DataFrame de manière sécurisée en passant par un fichier temporaire
    pour éviter de corrompre ou d'effacer le fichier original si le script plante.

    Arguments :
    dataframe (DataFrame) : Le DataFrame à sauvegarder.
    nom_fichier (Path) : Le chemin final du fichier CSV où sauvegarder le DataFrame.
    """
    if dataframe is None or dataframe.empty:
        print(f"\n\n Sécurité sauvegarde : Le DataFrame est vide ou invalide.\n Sauvegarde annulée.")
        return

    # S'assurer que les colonnes vitales n'ont pas disparu par erreur
    #if 'supercell_ID' not in dataframe.columns or 'pseudonyme' not in dataframe.columns:
    #    print(f"Sécurité sauvegarde : Colonnes critiques manquantes. \n Sauvegarde annulée.")
    #    return

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
        print(f"\n\n Une erreur s'est produite lors de la sauvegarde sécurisée : {e}")
        if os.path.exists(fichier_temp):
            try:
                os.remove(fichier_temp)
            except Exception:
                pass

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
    # Nettoyage et validation de l'identifiant
    identifiant = identifiant.strip('#')
    if not (6 <= len(identifiant) <= 10) or not identifiant.isalnum():
        print(f"\nL'identifiant est invalide. Il doit comporter entre 6 et 10 caractères alphanumériques.")
        return None

    # Configuration des URLs et des routes
    url_source = "https://proxy.royaleapi.dev/v1"
    # Cartographie des options pour éviter les blocs if/elif complexes
    routes = {
        "clan: info": f"{url_source}/clans/%23{identifiant}",
        "clan: membres": f"{url_source}/clans/%23{identifiant}/members",
        "guerre: actuelle": f"{url_source}/clans/%23{identifiant}/currentriverrace",
        "guerre: historique": f"{url_source}/clans/%23{identifiant}/riverracelog",
        "membre: info": f"{url_source}/players/%23{identifiant}",
        "membre: combats": f"{url_source}/players/%23{identifiant}/battlelog"
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

    # Exécution de la requête avec gestion des erreurs
    try:
        reponse = client.get(rep_cible, headers=en_tetes, timeout=10)

        # Lève automatiquement une exception pour les codes 4xx/5xx
        reponse.raise_for_status()
        print(f"\nConnexion réussi à l'API de Clash Royale via le lien\n {rep_cible}")
        return reponse.json()

    except requests.exceptions.HTTPError:
        status = reponse.status_code
        if status == 403:
            print(f"\nÉchec d'authentification (403). Vérifiez votre clé API et votre adresse IP.")
        elif status == 400:
            print(f"\nRequête incorrecte (400) : {reponse.text}")
        else:
            print(f"\nProblème API (Code {status}) : {reponse.text}")

    except requests.exceptions.RequestException as e:
        print(f"\nErreur réseau ou timeout : {e}")

    return None

def gdc_recente(clanTag, gdc_log_dic, semaine):
    """
    Fonction pour extraire les informations sur les membres qui ont participé à une guerre de clan récente.

    Paramètres :
    clanTag (str) : Identifiant Supercell du clan (doit commencer par '#').
    gdc_log_dic (dict) : Dictionnaire contenant l'historique des 10 dernières guerres de clan.
    semaine (int) : Un chiffre de 0 (guerre la plus récente) à 9 (guerre la plus ancienne)
                    spécifiant la semaine d'intérêt.

    Valeur de retour :
    pd.DataFrame : Un DataFrame Pandas contenant un résumé des résultats des participants,
                   trié par nombre de médailles décroissant.
    """
    # Vérification des entrées
    if not isinstance(gdc_log_dic, dict) or 'items' not in gdc_log_dic:
        raise ValueError("Le paramètre 'gdc_log_dic' doit être un dictionnaire contenant une clé 'items'.")

    if not isinstance(semaine, int) or semaine < 0 or semaine > 9:
        raise ValueError("Le paramètre 'semaine' doit être un entier entre 0 et 9.")

    # Créer des listes vides pour accumuler les informations des participants
    supercell_ID = []     # Identifiant Supercell des membres
    pseudonymes = []      # Pseudonyme des membres
    medailles = []        # Nombre de points contribuant à la renommée du clan
    pointsReparation = [] # Nombre de points contribuant à la réparation du bateau
    attaquesBateau = []   # Nombre de fois qu'un joueur à attaqué un bateau ennemi
    combats = []          # Nombre de combats effectués

    # Parcourir les standings de la semaine spécifiée pour trouver le clan correspondant
    try:
        for standing in gdc_log_dic['items'][semaine]['standings']:
            if clanTag.strip('#') == standing['clan']['tag'].strip('#'):
                # Parcourir les participants du clan trouvé
                for participant in standing['clan']['participants']:
                    supercell_ID.append(participant['tag'])
                    pseudonymes.append(participant['name'])
                    medailles.append(participant['fame'])
                    pointsReparation.append(participant['repairPoints'])
                    attaquesBateau.append(participant['boatAttacks'])
                    combats.append(participant['decksUsed'])
    except KeyError as e:
        raise KeyError(f"La structure du dictionnaire 'gdc_log_dic' est invalide. Clé manquante : {e}")

    # Créer un dictionnaire de listes
    data = {
        'supercell_ID': supercell_ID,
        'pseudonyme': pseudonymes,
        'médaille': medailles,
        'réparation_bateau': pointsReparation,
        'attaque_bateau': attaquesBateau,
        'no_combat': combats
    }

    # Convertir le dictionnaire en DataFrame Pandas et trier par nombre de médailles décroissant
    df = pd.DataFrame(data)
    return df.sort_values(by='médaille', ascending=False)

def gdc_log(clanTag, gdc_log_dic):
    """
    Fonction pour extraire les informations concernant les 10 dernières guerres de clan complétées.

    Paramètres :
    clanTag (str) : Identifiant Supercell du clan (doit commencer par '#').
    gdc_log_dic (dict) : Dictionnaire contenant l'historique des 10 dernières guerres de clan complétées.

    Valeur de retour :
    pd.DataFrame : Un DataFrame Pandas contenant un résumé des résultats des 10 dernières guerres.
    """
    # Vérification des entrées
    if not isinstance(gdc_log_dic, dict) or 'items' not in gdc_log_dic:
        raise ValueError("Le paramètre 'gdc_log_dic' doit être un dictionnaire contenant une clé 'items'.")

    # Initialiser la variable pour stocker les trophées actuels du clan
    clanWarTrophies = None

    # Trouver les trophées actuels du clan dans la guerre la plus récente
    for standing in gdc_log_dic['items'][0]['standings']:
        if clanTag.strip('#') == standing['clan']['tag'].strip('#'):
            clanWarTrophies = standing['clan']['clanScore'] + standing['trophyChange']
            break

    if clanWarTrophies is None:
        raise ValueError(f"Le clan avec l'identifiant {clanTag} n'a pas été trouvé dans les données.")

    # Initialiser les listes pour stocker les données
    saison = []  # Identifiant de la saison
    semaine = []  # Numéro de la semaine dans la saison
    date = []  # Date de fin de la guerre
    rang = []  # Rang du clan dans la guerre
    fame = []  # Points de renommée (fame) obtenus par le clan
    variation = []  # Variation des trophées après la guerre
    trophees = [clanWarTrophies]  # Trophées du clan après chaque guerre

    # Collecter les données des 10 dernières guerres complétées
    for item in gdc_log_dic['items']:
        saison.append(item['seasonId'])
        semaine.append(item['sectionIndex'] + 1)
        # Convertir la date de création en objet date et soustraire 7 jours pour obtenir la date de fin
        date.append(datetime.strptime(item['createdDate'], '%Y%m%dT%H%M%S.%fZ').date() - timedelta(days=7))

        # Trouver les informations du clan dans les standings
        for standing in item['standings']:
            if clanTag.strip('#') == standing['clan']['tag'].strip('#'):
                rang.append(standing['rank'])
                fame.append(standing['clan']['fame'])
                variation.append(standing['trophyChange'])
                # Calculer les trophées après la guerre en soustrayant la variation
                trophees.append(trophees[-1] - standing['trophyChange'])
                break

    # Créer un dictionnaire avec les données collectées
    data = {
        'date': date,
        'saison': saison,
        'semaine': semaine,
        'point_avancement': fame,
        'rang': rang,
        'variation': variation,
        'trophée': trophees[:-1]  # Exclure le dernier élément
    }

    # Créer un DataFrame Pandas à partir du dictionnaire
    return pd.DataFrame(data)

def ajout_resume(clanTag, gdc_log_dic, fichier):
    """
    Cette fonction ajoute le résumé de la dernière guerre complétée à
    un fichier `csv` contenant l'historique des guerres de clan passées.

    Paramètres :
    clanTag (str) : Identifiant Supercell du clan.
    clan_log_dic (dictionaire) : Contient l'historiques des 10 dernières guerres complétées.
    fichier (str) : Nom du fichier contenant l'historique.
    """
    
    # Lire le fichier `csv` contenant l'historique des guerres de clan passées
    historique_df = lecture_fichier_CSV(fichier)

    # Convertir la colonne 'date' en objet datetime
    historique_df['date'] = pd.to_datetime(historique_df['date'])

    # Obtenir les résultats de la semaine précédente
    gdc_log_df = gdc_log(clanTag, gdc_log_dic)
    semaine = 0 # semaine précédente
    gdc_precedente_df = gdc_recente(clanTag, gdc_log_dic, semaine)

    # Créer un dictionnaire contenant un résumé de la dernière semaine complétée
    addition = {
        'date': gdc_log_df.loc[0, 'date'],
        'saison': gdc_log_df.loc[0, 'saison'],
        'semaine': gdc_log_df.loc[0, 'semaine'],
        'point avancement': gdc_log_df.loc[0, 'point_avancement'],
        'rang': gdc_log_df.loc[0, 'rang'],
        'variation': gdc_log_df.loc[0, 'variation'],
        'trophée': gdc_log_df.loc[0, 'trophée'],
        'no_jours': 4,
        'combat_fait': gdc_precedente_df['no_combat'].sum(),  # Somme des combats faits
        'combat_manqué': 800 - gdc_precedente_df['no_combat'].sum(),  # Combats manqués
        'médaille': gdc_precedente_df['médaille'].sum()  # Somme des médailles
    }

    # Convertir le dictionnaire en DataFrame
    addition_df = pd.DataFrame([addition])

    # Convertir la colonne 'date' en objet datetime
    addition_df['date'] = pd.to_datetime(addition_df['date'])

    # Fusionner les DataFrames
    df = pd.concat([historique_df, addition_df], ignore_index=True)

    # Supprimer les doublons en gardant le dernier et mettre à jour le DataFrame en place
    df.drop_duplicates(subset=['date', 'saison', 'semaine'], keep='last', inplace=True)

    # Ordonner selon les dates en ordre décroissante
    df.sort_values('date', ascending=False, inplace=True)

    # Définir le chemin du fichier de sauvegarde
    file_to_save = dossier_fichiers / fichier
    sauvegarder_dataframe_csv(df, file_to_save)

def ajout_medailles(identifiant, clanTag, gdc_log_dic, fichier):
    """Met à jour l'historique des médailles de guerre d'un clan à partir du log de l'API
    de CLash Royale.

    Cette fonction extrait les 'médailles' des participants remportées lors des
    10 dernières semaines. Si le fichier de sauvegarde n'existe pas, elle l'initialise.
    S'il existe, elle fusionne les nouvelles données avec l'ancien historique pour la
    semaine ciblée.

    Paramètres
    ----------
    identifiant : str
        ID de la semaine cible à mettre à jour ou vérifier (ex: '133_5' pour Saison 133, Semaine 5).
    clanTag : str
        Le tag unique Supercell du clan (ex: '#LURGRP').
    gdc_log_dic : dict
        Données JSON brutes de l'API contenant l'historique des guerres.
    fichier : str ou Path
        Chemin du fichier CSV de destination contenant l'historique global.

    Returns
    -------
    None
        La fonction ne retourne rien, elle écrit directement les modifications
        dans un fichier CSV.

    Raises
    ------
    KeyError
        Si les structures attendues du dictionnaire de l'API (gdc_log_dic) sont absentes.
    """

    # =========================================================================
    # 1. EXTRACTION ET COMPILATION DES DONNÉES DE L'API
    # =========================================================================

    liste_df = []  # Stocke les DataFrames temporaires de chaque semaine détectée
    liste_semaines = []  # Liste ordonnée des identifiants de semaines trouvés

    # Parcours des guerres disponibles dans l'historique de l'API
    for item in gdc_log_dic["items"]:
        # Création de l'identifiant unique (Saison_Semaine)
        semaine_ID = f"{item['seasonId']}_{item['sectionIndex'] + 1}"

        for standing in item["standings"]:
            # Filtrage pour ne récupérer que les données du clan désiré
            if standing["clan"]["tag"].strip('#') == clanTag.strip('#'):
                liste_semaines.append(semaine_ID)

                # Extraction des données de chaque joueur
                participants = standing["clan"]["participants"]
                data = {
                    "supercell_ID": [p["tag"] for p in participants],
                    "pseudonyme": [p["name"] for p in participants],
                    semaine_ID: [p["fame"] for p in participants],
                }

                # Création du DataFrame hebdomadaire indexé par le joueur
                semaine_df = pd.DataFrame(data).set_index(["supercell_ID", "pseudonyme"])
                liste_df.append(semaine_df)

    if not liste_df:
        print("Aucune donnée trouvée dans l'API pour ce clan.")
        return

    # Fusion basée sur l'index (supercell_ID + pseudonyme)
    medailles10_df = pd.concat(liste_df, axis=1)

    # Re-ordonner les colonnes par chronologie inverse (la guerre la plus récente apparaît en dernier)
    liste_semaines = liste_semaines[::-1]
    medailles10_df = medailles10_df[liste_semaines]
    #medailles10_df.columns = liste_semaines[::-1]

    # Remettre l'index ("supercell_ID", "pseudonyme") en colonnes réelles
    medailles10_df = medailles10_df.reset_index()

    # Convertir les colonnes numériques extraites de l'API
    medailles10_df[liste_semaines] = medailles10_df[liste_semaines].astype("Int32")

    # Tri alphabétique des joueurs (insensible à la casse)
    medailles10_df = medailles10_df.sort_values(by="pseudonyme", key=lambda col: col.str.lower(), ascending=True)

    # =========================================================================
    # 2. SAUVEGARDE ET MISE À JOUR DE L'HISTORIQUE GLOBAL
    # =========================================================================

    # CAS A : Le fichier historique n'existe pas encore -> Initialisation complète
    if not os.path.exists(fichier):
        print(f"Le fichier {fichier} n'existe pas. Initialisation complète...")

        # Note : 'dossier_fichiers' doit être défini dans votre environnement global
        nom_fichier = Path(dossier_fichiers, f"{clan_dic['name']}_gdc_médailles.csv")
        sauvegarder_dataframe_csv(medailles10_df, nom_fichier)
        print("Historique des médailles remportées initialisé avec succès.\n")
        return

    # CAS B : Un historique existe -> Ajout/modification des données de la semaine cible
    else:
        # Vérification si la semaine demandée est présente dans l'extraction API
        if identifiant not in medailles10_df.columns.to_list():
            print(f"\nErreur : La semaine '{identifiant}' n'est pas disponible dans l'API.")
            return

        print(f"\nMise à jour de l'historique des médailles remportées pour la semaine : {identifiant}")
        medailles_df = lecture_fichier_CSV(fichier)

        # Vérifier si les médailles de la semaine précédente sont présentes dans le DataFrame
        if identifiant in medailles_df.columns:
            print("Les médailles de la semaine précédente seront mise-à-jour.")
            # Enlever la colonne cible
            medailles_df = medailles_df.drop(columns=identifiant, errors='ignore')

        # Fusion externe (Outer Join) basée sur l'identifiant Supercell du joueur
        medailles_df = pd.merge(medailles_df, medailles10_df[["supercell_ID", "pseudonyme", identifiant]], how="outer", on="supercell_ID")

        # En cas de nouveau joueur, on récupère son pseudonyme de l'API (_y) vers l'historique (_x)
        medailles_df["pseudonyme_x"] = medailles_df["pseudonyme_x"].fillna(medailles_df["pseudonyme_y"])

        # Consolidation de la mémoire du DataFrame après le merge (évite les avertissements de fragmentation)
        medailles_df = medailles_df.copy()

        # Nettoyage des colonnes résiduelles du merge
        medailles_df = medailles_df.drop(columns=["pseudonyme_y", "supercell_ID_y"], errors="ignore")
        medailles_df = medailles_df.rename(columns={"pseudonyme_x": "pseudonyme"})

        # Imposer le type de données pour les colonnes numériques
        for col in medailles_df.columns[2:]:
            # Forceer la conversion en numérique (transforme les espaces ' ' ou textes en NaN)
            medailles_df[col] = pd.to_numeric(medailles_df[col], errors="coerce").astype("Int32")

        # Tri final du fichier mis à jour par ordre alphabétique des joueurs
        medailles_df = medailles_df.sort_values(by="pseudonyme", key=lambda col: col.str.lower(), ascending=True)

        # Écriture finale sur le disque
        sauvegarder_dataframe_csv(medailles_df, fichier)

def gdc_current(clanTag, gdc_dic):
    """
    Fonction pour extraire les informations sur la guerre de clang en cours.

    Paramètres :
    clanTag (str) : Identifiant Supercell du clan.
    clan_dic (dic) : Dictionaire contenant les informations sur le clan

    Valeur de retour :
    dataframe : Un Pandas DataFrame contenant un résumé des résultats.
    """

    participants = gdc_dic.get('clan', {}).get('participants', [])

    # Construction du dictionnaire via des listes en compréhension
    data_dict = {
        'supercell_ID': [player['tag'] for player in participants],
        'pseudonyme': [player['name'] for player in participants],
        'médaille': [player['fame'] for player in participants],
        'attaque_bateau': [player['boatAttacks'] for player in participants],
        'no_combat_jours': [player['decksUsedToday'] for player in participants],
        'no_combat_total': [player['decksUsed'] for player in participants]
    }

    return pd.DataFrame(data_dict)

#def historique_quotidien(clanTag: str, gdc_dic: Dict[str, Any], gdc_log_dic: Dict[str, Any]) -> None:
#    """
#    Extrait et sauvegarde l'historique quotidien des guerres de clan pour la saison en cours.
#
#    Paramètres :
#        clanTag (str): Tag du clan (avec ou sans #)
#        gdc_dic (dict): Dictionaire contenant les informations de la guerre de clan en cours
#        gdc_log_dic (dict): Historique des guerres de clan complétées
#
#    Returns:
#        None: Génère un fichier CSV avec les résultats
#    """

#    # Déterminer la saison et la semaine de la guerre en cours.
#    semaine = gdc_dic['sectionIndex'] + 1 # Commence à zéro
#    saison = (gdc_log_dic['items'][0]['seasonId'] + 1) if semaine == 1 else gdc_log_dic['items'][0]['seasonId']

#    # Initialisation des conteneurs de données
#    donnees = {
#        'dates': [],
#        'gdc_ID': [],
#        'dates': [],
#        'medaille': [],
#        'rang': [],
#        'score': [],
#        'no_defense': [],
#        'defense': [],
#        'progres': []
#    }

#    # Dictionnaire de mapping nom du jour => plages de dates
#    calendrier = {
#        "j1": [3, 10, 17, 24, 31],
#        "j2": [4, 11, 18, 25, 32],
#        "j3": [5, 12, 19, 26, 33],
#        "j4": [6, 13, 20, 27, 34]
#    }

#    # boucler sur le nombre de jours de guerre complétés depuis le début de la saison
#    for i in range(len(gdc_dic['periodLogs'])):
#        # Obtenir l'indice associé aux nombres de jour écoulé depuis le début de la guerre
#        donnees['dates'].append(gdc_dic['periodLogs'][i]['periodIndex'])

#        # boucler sur le nombe de clans
#        for j in range(len(gdc_dic['periodLogs'][i]['items'])):
#            # Ajouter les données associées au clan d'intérêt
#            if gdc_dic['periodLogs'][i]['items'][j]['clan']['tag'].strip('#') == clanTag.strip('#'):
#                donnees['medaille'].append(gdc_dic['periodLogs'][i]['items'][j]['pointsEarned'])
#                donnees['rang'].append(gdc_dic['periodLogs'][i]['items'][j]['endOfDayRank'] + 1)
#                donnees['score'].append(gdc_dic['periodLogs'][i]['items'][j]['progressEarned'])
#                donnees['no_defense'].append(gdc_dic['periodLogs'][i]['items'][j]['numOfDefensesRemaining'])
#                donnees['defense'].append(gdc_dic['periodLogs'][i]['items'][j]['progressEarnedFromDefenses'])
#                donnees['progres'].append(gdc_dic['periodLogs'][i]['items'][j]['progressEndOfDay'])

#    # Construction des identifiants temporels
#    for date in donnees['dates']:
#        for nom_jour, dates_jour in calendrier.items():
#            if date in dates_jour:
#                semaine_cal = dates_jour.index(date) + 1
#                donnees['gdc_ID'].append(f"{saison}_{semaine_cal}_{nom_jour}")
#                break

#    # Enlever la clé 'dates'
#    donnees.pop('dates')

#    # Contruire un Pandas DataFrame et ordonner les rangées en ordre décroissant de 'gdc_ID'
#    resume_df = pd.DataFrame(donnees).sort_values('gdc_ID', ascending=False)

#    # Définition du nom du fichier de sauvegarde
#    dossier  = Path("C:/Users/schretien/Desktop/Clash_Royale")
#    base_nom = f"{gdc_dic['clan']['name']}_gdc_resume_quotidien"
#    fichier  = Path(dossier_fichiers, base_nom + '.csv')

#    # Vérifier l'existence du fichier et ajouter '_copie' si nécessaire
#    if fichier.exists():
#        print(f"Le fichier {fichier} existe déjà. Une copie sera sauvegardée.")
#        fichier_historique = Path(dossier_fichiers, base_nom + '_copie.csv')
#    else:
#        fichier_historique = fichier

#    # Sauvegarder dans un fichier
#    sauvegarder_dataframe_csv(resume_df, fichier_historique)

def historique_quotidien(clanTag: str, gdc_dic: Dict[str, Any], gdc_log_dic: Dict[str, Any]) -> None:
    """
    Extrait et sauvegarde l'historique quotidien des guerres de clan pour la saison en cours.

    Paramètres :
        clanTag (str): Tag du clan (avec ou sans #)
        gdc_dic (dict): Dictionaire contenant les informations de la guerre de clan en cours
        gdc_log_dic (dict): Historique des guerres de clan complétées

    Returns:
        None: Génère un fichier CSV avec les résultats
    """
    # Déterminer la saison et la semaine de la guerre en cours.
    semaine = gdc_dic['sectionIndex'] + 1
    saison = (gdc_log_dic['items'][0]['seasonId'] + 1) if semaine == 1 else gdc_log_dic['items'][0]['seasonId']

    # Dictionnaire de mapping nom du jour => plages de date
    calendrier = {
        "j1": [3, 10, 17, 24, 31],
        "j2": [4, 11, 18, 25, 32],
        "j3": [5, 12, 19, 26, 33],
        "j4": [6, 13, 20, 27, 34]
    }

    records = []

    for period in gdc_dic.get('periodLogs', []):
        period_index = period.get('periodIndex')
        
        # Recherche directe du clan dans les items de la période
        clan_item = next(
            (item for item in period.get('items', []) if item['clan']['tag'].strip('#') == clanTag.strip('#')), 
            None
        )

        if clan_item:
            # Identification du nom du jour et de la semaine du calendrier
            nom_jour = next((k for k, v in calendrier.items() if period_index in v), None)
            if nom_jour:
                semaine_cal = calendrier[nom_jour].index(period_index) + 1
                gdc_id = f"{saison}_{semaine_cal}_{nom_jour}"
                
                records.append({
                    'gdc_ID': gdc_id,
                    'medaille': clan_item.get('pointsEarned', 0),
                    'rang': clan_item.get('endOfDayRank', 0) + 1,
                    'score': clan_item.get('progressEarned', 0),
                    'no_defense': clan_item.get('numOfDefensesRemaining', 0),
                    'defense': clan_item.get('progressEarnedFromDefenses', 0),
                    'progres': clan_item.get('progressEndOfDay', 0)
                })

    # Construction du DataFrame
    resume_df = pd.DataFrame(records)
        
    if not resume_df.empty:
        # Convertir des colonnes en type de données 'Int32'
        for col in ['medaille', 'rang', 'score', 'no_defense', 'defense', 'progres']:
            resume_df[col] = pd.to_numeric(resume_df[col], errors='coerce').astype('Int32')
        # Ordonner les lignes en ordre croissant de guerre
        resume_df = resume_df.sort_values('gdc_ID', ascending=False)

    # Définition du nom du fichier de sauvegarde
    base_nom = f"{gdc_dic['clan']['name']}_gdc_resume_quotidien"
    fichier = Path(dossier_fichiers, base_nom + '.csv')
    
    if fichier.exists():
        print(f"Le fichier {fichier} existe déjà. Une copie sera sauvegardée.")
        fichier_historique = Path(dossier_fichiers, base_nom + '_copie.csv')
    else:
        fichier_historique = fichier

    sauvegarder_dataframe_csv(resume_df, fichier_historique)
########

def actualiser_historique(clanTag, gdc_dic, clan_log_dic):
    """
    Extrait et sauvegarde l'historique de la denière journée de guerre de clan complétée.

    Paramètres :
        clanTag (str): Tag du clan (avec ou sans #)
        gdc_dic (dict): Dictionaire contenant les informations de la guerre de clan en cours
        gdc_log_dic (dict): Historique des guerres de clan complétées

    Returns:
        None: Mise à jour d'un fichier CSV contenant l'historique quotidien des guerres passées.
    """

    try:
        # Définition du nom des fichiers d'ouverture et de sauvegarde
        fichier_resume = Path(dossier_fichiers, gdc_dic['clan']['name'] + '_gdc_resume_quotidien.csv')
        # Lire le fichier CSV contenant l'historique quotidien des jours de guerre
        historique_df = pd.read_csv(fichier_resume)
        print(f"Le fichier {fichier_resume} a été lu.")

         # Convertir des colonnes en type de données 'Int32'
        for col in ['medaille', 'rang', 'score', 'no_defense', 'defense', 'progres']:
            historique_df[col] = pd.to_numeric(historique_df[col], errors='coerce').astype('Int32')

        # L'historique de guerre n'est pas disponible pendant le Colisée ainsi que pendant
        # l'entraînement de la première semaine. En d'autres mots, gdc_dic['periodLogs'] est
        # créé lors du premier jour de guerre et disparaît lors du premier jour de combat dans le Colisée.
        if (gdc_dic['periodType'] == 'colosseum') or ((gdc_dic['sectionIndex'] + 1 == 1) and (gdc_dic['periodType'] == 'training')):
            print("Le clan est dans le Colisée. Auncune information ne sera ajouté au fichier contenant l'historique quotidien")
        else:
            for i in range(len(gdc_dic['periodLogs'][-1]['items'])):
                if gdc_dic['periodLogs'][-1]['items'][i]['clan']['tag'].strip('#') == clanTag.strip('#'):
                    # Créer un dictonaire contenant les informations de la journée précédente
                    dictionaire = {'gdc_ID': jour_dic[id_jour][0],
                                   'medaille': gdc_dic['periodLogs'][-1]['items'][i]['pointsEarned'],
                                   'rang': gdc_dic['periodLogs'][-1]['items'][i]['endOfDayRank'] + 1,
                                   'score': gdc_dic['periodLogs'][-1]['items'][i]['progressEarned'],
                                   'no_defense': gdc_dic['periodLogs'][-1]['items'][i]['numOfDefensesRemaining'],
                                   'defense': gdc_dic['periodLogs'][-1]['items'][i]['progressEarnedFromDefenses'],
                                   'progres': gdc_dic['periodLogs'][-1]['items'][i]['progressEndOfDay'],
                                   #'combat': df[jour_dic[id_jour][0]].sum(axis=0)
                                  }
                    break

            # Convertir le dictionaire en Pandas Dataframe
            hier_df = pd.DataFrame([dictionaire])

            # Ajouter le résumé de la journée de guerre précédente à l'historique de guerre
            historique_df = pd.concat([historique_df, hier_df], axis=0, ignore_index=True)

            # Supprimer les doublons en gardant le dernier et mettre à jour le DataFrame en place
            historique_df.drop_duplicates(subset=['gdc_ID'], keep='last', inplace=True)

            # Ordonner selon les dates en ordre décroissante
            historique_df.sort_values('gdc_ID', ascending=False, inplace=True)

            sauvegarder_dataframe_csv(historique_df, fichier_resume)

    except FileNotFoundError:
        print(f"Le fichier {fichier_resume} n'a pas été trouvé.")
        # Créer le fichier contenant l'historique quotidien des jours de guerre
        historique_quotidien(clanTag, gdc_dic, gdc_log_dic)

def participations_partielles(df, nom_col, nom_fichier):
    """
    Traite les participations partielles à partir d'un DataFrame.

    Args:
        df (pd.DataFrame): DataFrame contenant la participation quotidienne aux gdc.
        nom_col (str): Nom de la colonne contenant les données de participation à analyser.
        nom_fichier (Path): Chemin pointant sur le fichier CSV contenant les notes.

    Returns:
        None
    """

    # Filtrer le DataFrame pour obtenir les participations partielles (valeurs > 0 et != 4)
    partielle_df = df[(df[nom_col] > 0) & (df[nom_col] != 4)][['supercell_ID', 'pseudonyme', nom_col]]
    print(partielle_df)

    if not partielle_df.empty: # Vérifier si le DataFrame n'est pas vide
        partielle_df['date'] = date.today().strftime('%Y-%m-%d')
        partielle_df['action'] = 'participation partielle'
        partielle_df['commentaire'] = partielle_df[nom_col].apply(lambda x: f"{int(x)} combat(s) fait(s) sur 4")
        partielle_df.drop(labels=nom_col, axis=1, inplace=True)

        # Lire le fichier CSV contenant les notes existantes
        notes_df = lecture_fichier_CSV(nom_fichier)

        # Concaténer les DataFrames des notes existantes et des participations partielles
        notes_df = pd.concat([notes_df, partielle_df], axis=0, ignore_index=True)

        # Supprimer les lignes dupliquées (en conservant la première occurrence)
        notes_df.drop_duplicates(inplace=True)

        # Trier le DataFrame par `date` en ordre décroissant
        notes_df.sort_values('date', ascending=False, inplace=True)

        # Sauvegarder les notes
        sauvegarder_dataframe_csv(notes_df, nom_fichier)

def membres_info(clanTag, clan_dic):
    """
    Fonction pour extraire les informations sur les membres actuels du clan à partir de l'API de Clash Royale.

    Paramètres :
    clanTag (str) : Identifiant Supercell du clan.
    clan_dic : Dictionaire contenant l'information générale sur un clan

    Valeur de retour :
    dataframe : Un Pandas DataFrame contenant un résumé des résultats.
    """

    # Création d'un DataFrame à partir de la liste des membres
    membres_df = pd.DataFrame(clan_dic['memberList'])

    # Effacer les colonnes sans intérêt
    membres_df = membres_df.drop(columns=['previousClanRank', 'clanChestPoints'])

    # Traduction des rôles en français
    role_dic = {'member': 'membre', 'elder': 'aîné', 'coLeader': 'chef adjoint', 'leader': 'chef'}
    membres_df['role'] = membres_df['role'].map(role_dic)

    # Extraire la dernière arène atteinte (en prenant en compte l'ID)
    membres_df['arena'] = membres_df['arena'].apply(lambda x: x['id'] - 53999997)

    # Renommer les colonnes en français
    colonnes = ['supercell_ID', 'pseudonyme', 'rôle', 'connexion', 'expérience', 'trophées', 'arène', 'rang', 'donation', 'don reçue']
    membres_df.columns = colonnes

    # Calculer le temps écoulé depuis la dernière connexion sans les millisecondes
    membres_df['connexion'] = membres_df['connexion'].apply(lambda x: temps_ecoule(x))

    # Définir 'rang' comme index
    membres_df.set_index('rang', inplace=True)

    return membres_df

def temps_ecoule(temps_UTC):
    """
    Calcule le temps écoulé depuis la dernière connexion à partir d'un temps UTC donné.

    Args:
        temps_UTC (str): Chaîne de caractères représentant le temps UTC au format '%Y%m%dT%H%M%S.%fZ'.

    Returns:
        str: Temps écoulé formaté de manière lisible (ex: "2 jours 5h", "43 min", etc.).
    """
    try:
        # Conversion du texte en objet datetimee
        date_api = datetime.strptime(temps_UTC, '%Y%m%dT%H%M%S.%fZ').replace(tzinfo=timezone.utc)
        difference = datetime.now(timezone.utc) - date_api

        total_secondes = int(difference.total_seconds())

        # Sécurité : Si le temps est dans le futur à cause d'un décalage d'horloge
        if total_secondes <= 0:
            return "À l'instant"

        jours, reste_secondes = divmod(total_secondes, 86400) # 86400 secondes par jour
        heures, reste_secondes = divmod(reste_secondes, 3600)
        minutes, secondes = divmod(reste_secondes, 60)

        # Retourne le format le plus pertinent
        if jours > 0:
            return f"{jours}j {heures}h"
        elif heures > 0:
            return f"{heures}h {minutes}min"
        elif minutes > 0:
            return f"{minutes}min"
        else:
            return f"{secondes}sec"

    except (ValueError, TypeError):
        # Le membre n'a jamais ouvert le jeu depuis son entrée ou la chaîne est invalide
        return "--"

# ================================================
# Requêtes pour obtenir les informations d'un clan
# ================================================

# Identifiant Supercell (avec ou sans le '#')
clanTag = 'LURGRP' # Lausannegeles
#clanTag    = 'PV2PR2JY' # Lausannegeles2
#clanTag    = 'Y98YRLCL' # Les Tokkards

# Ouvrir une session réutilisable
with requests.Session() as ma_session:

    # Obtenir l'information générale d'un clan
    clan_dic = requete_API(ma_cle, clanTag, 'clan: info', session=ma_session)

    # Obtenir l'information de la guerre de clan en cours
    gdc_dic = requete_API(ma_cle, clanTag, 'guerre: actuelle', session=ma_session)

    # Obtenir l'information des guerres de clan passées
    gdc_log_dic = requete_API(ma_cle, clanTag, 'guerre: historique', session=ma_session)

# =============================
# Résumé de la journée en cours
# =============================

# Créer un pandas DataFrame contenant les résultats de la guerre en cours
gdc_df = gdc_current(clanTag, gdc_dic)

if gdc_dic['periodType'] in ['warDay', 'colosseum']:
    print("Résumé de la journée jusqu'à présent\n")

    # Créer un Pandas DataFrame contenant les informations sur les membres présent dans le clan
    membres_df = membres_info(clanTag, clan_dic)

    # Liste des membres présents dans le clan
    membres = membres_df['pseudonyme'].to_list()

    # Nombre de médailles accumulées
    medailles_total = gdc_df['médaille'].sum()
    print(f"   - {medailles_total} médailles")

    # Nombre total de participants
    participants_total = (gdc_df['no_combat_jours'] != 0).sum()
    print(f"   - {participants_total} membres ont participé à la guerre")

    # Membres ayant complété toutes leurs attaques de guerre
    combats_completes = (gdc_df['no_combat_jours'] == 4).sum()
    print(f"   - {combats_completes} membres ont fait leurs 4 combats de guerre")

    # Membres ayant partiellement participé à la guerre
    no_partiel = ((gdc_df['no_combat_jours'] > 0) & (gdc_df['no_combat_jours'] != 4)).sum()
    print(f"   - {no_partiel} membres ont participé partiellement à la guerre")

    # Membres n'ayant pas participé à la guerre
    no_zero = ((gdc_df['pseudonyme'].isin(membres)) & (gdc_df['no_combat_jours'] == 0)).sum()
    print(f"   - {no_zero} membres n'ont pas participé à la guerre")

    if no_partiel > 0:
        print("\nListe des membres ayant participé partiellement aujourd'hui")
        partiellement_df = gdc_df[(gdc_df['no_combat_jours'] > 0) & (gdc_df['no_combat_jours'] < 4)]
        print(partiellement_df[['pseudonyme', 'médaille', 'no_combat_jours']])

    if no_zero > 0:
        print("\nListe des membres n'ayant pas participé à la guerre aujourd'hui")
        non_participation_df = gdc_df[(gdc_df['pseudonyme'].isin(membres)) & (gdc_df['no_combat_jours'] == 0)]
        print(non_participation_df['pseudonyme'])
else:
    print("Journée d'entraînement. Amusez-vous!")

# Obtenir le temps et la date actuels
current_time = datetime.now(timezone.utc).time()
current_date = datetime.now(timezone.utc).date()

# ====================================
# Mettre à jour les statisques de clan
# ====================================

# Définir quelques listes de dates
training_dates = sorted(list(range(0, 35, 7)) + list(range(1, 35, 7)) + list(range(2, 35, 7)))
j1_dates = list(range(3, 35, 7))
j2_dates = list(range(4, 35, 7))
j3_dates = list(range(5, 35, 7))
j4_dates = list(range(6, 35, 7))

# Définition du nom des fichiers d'ouverture et de sauvegarde
fichier_combats = dossier_fichiers / (clan_dic['name'] + '_gdc_combats.csv')

try:
    # Lire le fichier CSV contenant l'historique du nombre de combats quotidiens
    combats_df = pd.read_csv(fichier_combats)
    print(f"\nLe fichier {fichier_combats} a été lu.")

    # Remplir les valeurs manquantes avec np.nan
    combats_df = combats_df.fillna(np.nan)

    # Convertir les colonnes correspondantes aux jours de guerre en type de données 'Int32'
    for col in combats_df.columns:
        if '_j' in col:
            # Convertir les valeurs non numériques en NaN avant la conversion en Int32
            combats_df[col] = pd.to_numeric(combats_df[col], errors='coerce').astype('Int32')
except FileNotFoundError:
    print(f"\nLe fichier {file_to_open} n'a pas été trouvé.")
    combats_df = pd.DataFrame()

if not combats_df.empty:

    if (gdc_dic['periodType'] == 'training') or (gdc_dic['periodIndex'] in j1_dates):
        """
        En période d'entraînement, les combats quotidiens ne sont pas compilés.
        Par contre, il faut compiler les combats effectués lors de la dernière
        journée de guerre.
        """
        # Déterminer la saison et la semaine de la dernière guerre complétée.
        saison = gdc_log_dic['items'][0]['seasonId']
        semaine = gdc_log_dic['items'][0]['sectionIndex'] + 1 # Commence à zéro

        # Mettre à jour le fichier contenant l'historique des guerres précédentes
        fichier_historique = Path(dossier_fichiers, clan_dic['name'] + '_gdc_historique.csv')
        ajout_resume(clanTag, gdc_log_dic, fichier_historique)

        # Mettre à jour le fichier contenant les médailles remportées hebdomadairement par les membres
        fichier_medailles = Path(dossier_fichiers, clan_dic['name'] + '_gdc_médailles.csv')
        identifiant = f"{saison}_{semaine}"
        ajout_medailles(identifiant, clanTag, gdc_log_dic, fichier_medailles)

        # Déterminer la saison de la guerre précédente
        saison =  gdc_log_dic['items'][0]['seasonId']
        # Détermines la semaine de la guerre précédente (commence à zéro et non à un)
        semaine = gdc_log_dic['items'][0]['sectionIndex'] + 1

        # Obtenir les résultats de la dernière guerre complétée
        gdc_info_df = gdc_recente(clanTag, gdc_log_dic, 0)

        # Sélectioner les colonnes d'intérêt
        gdc_info_df =  gdc_info_df[['supercell_ID', 'no_combat', 'pseudonyme']]

        # Définir la liste des colonnes temporaires
        colonnes_temp = ['pseudonyme_y', 'no_combat']

        # Déterminer pour quelle journée nous devons calculer les combats effectués
        id_jour = 'j4'
        print('Compilation des combats effectués lors de la dernière journée de guerre de la semaine précédente')


    elif (gdc_dic['periodType'] != 'training') and (gdc_dic['periodIndex'] not in j1_dates):
        """
        Pendant une journée de guerre (sauf le jeudi), nous compilons les combats effectués
        lors de la journée précédente.
        """
        print('Journée de guerre! Compilons les combats effectués lors de la dernière journée de guerre précédente')

        # Déterminer la saison et la semaine de la guerre en cours.
        semaine = gdc_dic['sectionIndex'] + 1 # Commence à zéro
        if semaine == 1:
            saison = gdc_log_dic['items'][0]['seasonId'] + 1
        else:
            saison = gdc_log_dic['items'][0]['seasonId']

        # Obtenir les résultats de la semaine en cours
        gdc_info_df = gdc_current(clanTag, gdc_dic)

        # Définir la liste des colonnes temporaires
        colonnes_temp = ['pseudonyme_y', 'médaille', 'attaque_bateau', 'no_combat_jours', 'no_combat_total']

        # Déterminer pour quelle journée nous devons calculer les combats effectués
        if gdc_dic['periodIndex'] in j2_dates: # deuxième journée de guerre
            id_jour = 'j1'
            print('Compilation des résultats de la première journée de guerre')

        elif gdc_dic['periodIndex'] in j3_dates: # troisième journée de guerre
            id_jour = 'j2'
            print('Compilation des résultats de la deuxième journée de guerre')

        elif gdc_dic['periodIndex'] in j4_dates: # quatrième journée de guerre
            id_jour = 'j3'
            print('Compilation des résultats de la troisième journée de guerre')

    else:
        print("Le type de journée de guerre n'a pas été identifié correctement")

    # Définir les noms des colonnes associées à la guerre précédente
    nom_j1 = str(saison) + '_' + str(semaine) + '_' + 'j1'
    nom_j2 = str(saison) + '_' + str(semaine) + '_' + 'j2'
    nom_j3 = str(saison) + '_' + str(semaine) + '_' + 'j3'
    nom_j4 = str(saison) + '_' + str(semaine) + '_' + 'j4'
    noms   = [nom_j1, nom_j2, nom_j3, nom_j4]

    # Fusionner les dataframes
    df = pd.merge(combats_df, gdc_info_df, how='outer', on='supercell_ID')

    # Créer un dictionaire reliant le type de journée et la colonne à ajouter au dataframe
    jour_dic = {'j1': [nom_j1, 'no_combat_total', 'no_combat_jours'],
                'j2': [nom_j2, 'no_combat_total', 'no_combat_jours', nom_j1],
                'j3': [nom_j3, 'no_combat_total', 'no_combat_jours', nom_j1, nom_j2],
                'j4': [nom_j4, 'no_combat', nom_j1, nom_j2, nom_j3]}

    # Calculer le nombre de decks employés par chaque membre lors de la dernière journée de guerre complétée
    df[jour_dic[id_jour][0]] = (df[jour_dic[id_jour][1]] - df[jour_dic[id_jour][2:]].sum(axis=1, skipna=True)).astype('Int32', errors='ignore')

    # Créer une liste des membres actuels du clan
    membres_df = membres_info(clanTag, clan_dic)
    membres_actuels = membres_df['supercell_ID'].to_list()

    # Créer une liste de tous les membres présent dans l'historique des combats de guerre
    membres_complet = df['supercell_ID'].to_list()

    # Créer une liste des membres absents
    membres_absence = [membre for membre in membres_complet if membre not in membres_actuels]

    # Remplacer le nombre de combat par 'np.nan' pour les membres absents n'ayant pas participé
    df.loc[(df[jour_dic[id_jour][0]] == 0) & (df['supercell_ID'].isin(membres_absence)), jour_dic[id_jour][0]] = np.nan

    # En cas de nouveau joueur, on récupère son pseudonyme de l'API (_y) vers l'historique (_x)
    df['pseudonyme_x'] = df['pseudonyme_x'].fillna(df['pseudonyme_y'])

    # Enlever les colonnes temporaires
    df = df.drop(columns=colonnes_temp, errors='ignore')

    # Renommer la colonne contenant les pseudonymes
    df = df.rename(columns={'pseudonyme_x':'pseudonyme'})

    # Ordonner les rangées en ordre alphabétique croissant de pseudonym (en ignorant la casse)
    df.sort_values(by='pseudonyme', ascending=True, key=lambda col: col.str.lower(), inplace=True)

    # Convertir les colonnes correspondantes aux jours de guerre en type de données 'Int32'
    for col in df.columns:
        if '_j' in col:
            # Convertir les valeurs non numériques en NaN avant la conversion en Int32
            df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int32')

    # Sauvegarder les résultats dans un fichier CSV
    sauvegarder_dataframe_csv(df, fichier_combats)

    # Mettre a jour le fichier contenant l'historique de guerre quotidien
    actualiser_historique(clanTag, gdc_dic, gdc_log_dic)

    # Afficher le résumé de la journée précédente
    print(f'Résumé de la journée précédente')
    print(31*'=')
    print(f'{df.iloc[:, -1].sum()} combats faits')
    print(f'{200 - df.iloc[:, -1].sum()} combat(s) manqué(s)')

    # Identifier les membres ayant participé partiellement
    n_partiel = df[(df.iloc[:, -1] > 0) & (df.iloc[:, -1] != 4)].shape[0]
    if n_partiel == 0:
        print('Aucune participation partielle')
    else:
        print(f"\nVoici la liste des membres ayant participé partiellement")

        # Définir le chemin menant au fichier contenant les notes sur le clan
        fichier_notes = Path(dossier_fichiers, f"{clan_dic['name']}_notes.csv")
        # Ajouter les participations partielles aux `notes` sur le clan
        participations_partielles(df, jour_dic[id_jour][0], fichier_notes)