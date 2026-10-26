#!/usr/bin/env python
# coding: utf-8

"""
Compilation des donations hebdomadaires.

Ce programme Python est conçu pour automatiser:
    - la récupération des données de donation hebdomadaire d'un clan Clash Royale via l'API,
    - le maintien d'un historique de ces donations dans un fichier CSV
    - affichage du total des donations pour la semaine en cours.
"""
import numpy as np
import pandas as pd
import datetime
import logging
import os
import sys
import requests
from pathlib import Path
import urllib.parse

# Setup logging config so errors actually print to console
logging.basicConfig(level=logging.INFO)


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
    if not (6 <= len(identifiant) <= 9) or not identifiant.isalnum():
        print(f"L'identifiant est invalide. Il doit comporter entre 6 et 9 caractères alphanumériques.")
        return None

    # Configuration des URLs et des routes
    url_source = "https://proxy.royaleapi.dev/v1"
    # Cartographie des options pour éviter les blocs if/elif complexes
    routes = {
        "clan: info": f"{url_source}/clans/%23{identifiant}",
        "clan: membres": f"{url_source}/clans/%23{identifiant}/members",
        "guerre: actuelle": f"{url_source}/clans/%23{identifiant}/currentriverrace",
        "guerre: historique": f"{url_source}/clans/%23{identifiant}/riverracelog"
    }

    if option not in routes:
        print(f"L'option '{option}' n'est pas valide.")
        print(f"Options disponibles : {list(routes.keys())[1:]}")
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
        print(f"Connexion réussi à l'API de Clash Royale via le lien\n {rep_cible}")
        return reponse.json()

    except requests.exceptions.HTTPError:
        status = reponse.status_code
        if status == 403:
            print("Échec d'authentification (403). Vérifiez votre clé API et votre adresse IP.")
        elif status == 400:
            print(f"Requête incorrecte (400) : {reponse.text}")
        else:
            print(f"Problème API (Code {status}) : {reponse.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"Erreur réseau ou timeout : {e}")

    return None

# =============================================================

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

# =============================================================
    
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
    if 'supercell_ID' not in dataframe.columns or 'pseudonyme' not in dataframe.columns:
        print(f"\n\n Sécurité sauvegarde : Colonnes critiques manquantes. \n Sauvegarde annulée.")
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
            print(f"\n\n Le DataFrame a été sauvegardé avec succès et en toute sécurité dans\n {nom_fichier}.")
    except (IOError, OSError) as e:
        print(f"\n\n Une erreur s'est produite lors de la sauvegarde sécurisée : {e}")
        if os.path.exists(fichier_temp):
            try:
                os.remove(fichier_temp)
            except Exception:
                pass

# =============================================================

def nettoyer_et_convertir_donnees(df):
    """
    Nettoie les colonnes d'un DataFrame à partir de la 3ème colonne :
        - supprime les espaces superflus pour les chaînes de caractères,
        - remplace les chaînes vides par des valeurs NaN, et convertit le tout en entiers.

    Parameters:
    -----------
    df : pd.DataFrame
        Le DataFrame contenant les données à nettoyer.

    Returns:
    --------
    pd.DataFrame
        Le DataFrame modifié avec les colonnes nettoyées et converties.
    """
    # Sélectionner toutes les colonnes à partir de la 3ème (index 2)
    col_numerique = df.columns[2:]
    
    # Enelever les espaces pour les colonnes de type texte (object)
    for col in col_numerique:
        if df[col].dtype == 'object':
            df[col] = df[col].str.strip()
            
    # Remplacer les chaînes vides ou espaces par NaN, puis convertir ces colonnes en type entier
    df[col_numerique] = df[col_numerique].replace(r'^\s*$', np.nan, regex=True).fillna(np.nan).astype('Int32')
    
    return df

# =============================================================

# Détection de l'environnement
if 'google.colab' in sys.modules:
    from google.colab import drive
    
    # Monte le Drive uniquement s'il n'est pas déjà monté
    if not os.path.exists('/content/drive/MyDrive'):
        drive.mount('/content/drive')
    else:
        print("Google Drive est déjà monté.")
        
    dossier_fichiers = Path("/content/drive/MyDrive/Clash_Royale")
    print("Mode détecté : Google Colab")
else:
    # Répertoire de base sur l'ordinateur
    dossier_fichiers = Path("C:/Users/schretien/Desktop/Clash_Royale")
    print("Mode détecté : Local (Ordinateur)")

print(f"Dossier de travail configuré : {dossier_fichiers}")

# Définir la clé API
cle_API = dossier_fichiers / "CR_API_proxy.txt"

# Vérifier que le fichier existe
if not os.path.exists(cle_API):
    raise FileNotFoundError(
        f"Error: Le fichier '{cle_API}' contenant la clé API n'existe pas à l'endroit attendu.")

with open(cle_API, "r") as file:
    ma_cle = file.read().rstrip("\n")
 
# S'assurer que le script s'arrête si la clé n'a pas pu être récupérée
if ma_cle:
    # Définir le répertoire où les résultats sont compilés
    #dossier_fichiers  = Path("C:/Users/schretien/Desktop/Clash_Royale")
    
    # Définir l'identifiant Supercell du clan (avec ou sans le #)
    clanTag = 'LURGRP' # Lausannegeles
    #clanTag    = 'PV2PR2JY' # Lausannegeles2
    #clanTag    = 'Y98YRLCL' # Les Tokkards

    with requests.Session() as ma_session:
        # Obtenir l'information générale d'un clan
        clan_dic = requete_API(ma_cle, clanTag, 'clan: info', session=ma_session)

        if clan_dic:
            print(f"Succès ! Nom du clan récupéré : {clan_dic.get('name')}")
    nom_clan = clan_dic['name'] # nom du clan
    membres = clan_dic['memberList'] # liste des membres actuels du clan

    # Créer un pandas DataFramecontenant les donations de la semaine en cours
    donations_df = pd.DataFrame(clan_dic['memberList'])[['tag', 'name', 'donations']]
    donations_df.columns = ['supercell_ID', 'pseudonyme', 'dons']
    print(donations_df.head(10))

    # Obtenir la date d'aujourd'hui selon le temps UTC
    aujourdhui = datetime.datetime.now(datetime.UTC).date()

    # Obtenir la date du prochain lundi
    prochain_lundi = aujourdhui + datetime.timedelta(days = 7 - aujourdhui.weekday())
    #print(f"La date du prochain lundi sera : {prochain_lundi}")

    # Définition du nom des fichiers d'ouverture et de sauvegarde
    fichier_dons = Path(dossier_fichiers, clan_dic['name'] + '_dons.csv')

    # =====
    # Si le fichier n'existe pas, on initialise l'historique avec les données de la semaine
    if not os.path.exists(fichier_dons):
        print(f"Le fichier {fichier_dons} n'existe pas. Création du fichier initial.")
                
        # On renomme temporairement 'dons' avec la date du lundi pour avoir la bonne structure de colonne
        donations_initial_df = donations_df.rename(columns={'dons': str(prochain_lundi)})
                
        # Sauvegarde les donations de la semaine
        sauvegarder_dataframe_csv(donations_initial_df, fichier_dons)
                
    # Si le fichier existe, mettre à jour l'historique
    else:
        try:
            # Lire le fichier CSV contenant l'historique des donations
            historique_donations_df = lecture_fichier_CSV(fichier_dons)

            if historique_donations_df is not None:
                # Fusionner les dataframes
                df = pd.merge(historique_donations_df, donations_df, how='outer', on='supercell_ID')

                # Ajouter les pseudonymes manquants au besoin
                df['pseudonyme_x'] = df['pseudonyme_x'].fillna(df['pseudonyme_y'])

                # Défragmenter le DataFrame
                df = df.copy()
                        
                # Créer une colonne contenant les pseudonymes en lettre minuscule
                df['pseudonyme_lower'] = df['pseudonyme_x'].str.lower()
                    
                # Ordonner les rangées en ordre alphabétique croissant
                df.sort_values(by='pseudonyme_lower', ascending=True, inplace=True)
                        
                if str(prochain_lundi) in list(historique_donations_df.columns):
                    # Corriger les donations des membres qui ont quitté après avoir donné des cartes.
                    df['dons'] = np.where(pd.notnull(df[str(prochain_lundi)]) & df['dons'].isna(),
                                                     df[str(prochain_lundi)],
                                                     df['dons'])
                       
                    # Corriger les donations des membres qui ont quitté, puis rejoint le clan
                    df[str(prochain_lundi)] = np.where(df[str(prochain_lundi)] > df['dons'],
                                                        df[str(prochain_lundi)] + df['dons'],
                                                        df['dons'])

                    col_noms = {'pseudonyme_x':'pseudonyme'} 
                    col_rejet = ['pseudonyme_y', 'dons', 'pseudonyme_lower']
                else:
                    col_noms = {'pseudonyme_x':'pseudonyme', 'dons': str(prochain_lundi)}
                    col_rejet = ['pseudonyme_y', 'pseudonyme_lower']

                # Renommer et nettoyer
                df = df.rename(columns=col_noms)
                df.drop(columns=col_rejet, errors='ignore', inplace=True)

                # Nettoyer et convertir les colonnes numériques
                df = nettoyer_et_convertir_donnees(df)

                # Afficher les donations de la semaine en cours
                print(f"Total des donations de la semaine: {df[str(prochain_lundi)].sum()}")

                # Sauvegarde sécurisée du Dataframe modifié
                sauvegarder_dataframe_csv(df, fichier_dons)
            else:
                print("Erreur : Impossible de mettre à jour car l'historique n'a pas pu être lu.")

        except Exception as e:
            print(f"Une erreur est survenue lors du traitement : {e}")
else:
    logging.error("Impossible de lancer la requête car la clé API est absente.")