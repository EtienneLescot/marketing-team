# Politique de Confidentialité de l'Application d'Orchestration Marketing IA

**Date d'entrée en vigueur :** 15 Décembre 2025

Cette Politique de Confidentialité s'applique à l'application d'orchestration d'agents IA (nommée ci-après, "l'Application d'Orchestration"), un outil développé pour générer et gérer le contenu marketing (posts LinkedIn, Medium, etc.) pour le projet Stimm.

---

## 1. Nature et Objet de l'Application

L'Application d'Orchestration est un outil **interne** (ou à usage limité) conçu pour :
* Orchestrer des agents IA (via LangGraph) pour la création de contenu marketing.
* Automatiser la publication de ce contenu sur des plateformes externes comme LinkedIn.

## 2. Données Collectées et Traitées

L'Application d'Orchestration accède et traite les catégories de données suivantes :

| Catégorie de Données | Source | But de la Collecte et du Traitement |
| :--- | :--- | :--- |
| **Données de Création de Contenu** | Entrées utilisateur (sujets, tons, objectifs marketing). | Utilisation par les agents IA pour générer le contenu (texte des posts). |
| **Identifiants de Publication** | Token d'accès OAuth (ex: LinkedIn). | Authentification nécessaire pour l'Application afin de publier le contenu généré sur les plateformes cibles. |
| **Données de Tiers (LLM)** | Prompts et réponses des API des Modèles de Langage (OpenAI, Mistral, etc.). | Nécessaire pour l'exécution du service de génération de contenu via LangGraph. |

## 3. Utilisation des Données

Les données sont utilisées **exclusivement** pour :
* Fournir le service d'orchestration d'agents IA (LangGraph).
* Publier le contenu généré par l'IA sur les réseaux sociaux autorisés.
* Déboguer et améliorer les chaînes d'agents.

## 4. Partage des Données

* **Fournisseurs d'IA (Tiers) :** Le contenu (prompts et réponses) est transmis aux fournisseurs d'API LLM (Mistral, OpenAI, etc.) nécessaires à l'exécution de LangGraph. Ces tiers traitent les données conformément à leurs propres politiques de confidentialité.
* **Plateformes de Publication :** Le contenu final (le post) et le token d'accès sont transmis à la plateforme choisie (ex: LinkedIn) pour la publication.
* **Vente :** Les données collectées ne sont **en aucun cas vendues** ou partagées à des fins de marketing tiers.

## 5. Stockage et Sécurité

Nous nous engageons à stocker les tokens d'accès (ex: LinkedIn) de manière sécurisée (chiffrement) et à minimiser la durée de rétention des données de création de contenu.

---

## 6. Contact

Pour toute question concernant cette politique, veuillez contacter le mainteneur du projet Stimm via son dépôt GitHub.