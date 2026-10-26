"""Domaines, consignes système et base documentaire de démonstration.

Les documents sont volontairement courts et génériques : ils servent de
sources vérifiables pour l'assistant et peuvent être complétés depuis
l'interface. Ils ne remplacent pas une documentation officielle.
"""

DOMAINS = [
    {
        "slug": "general",
        "label": "Général",
        "icon": "✦",
        "description": "Assistant polyvalent pour vos questions du quotidien.",
        "system_prompt": (
            "Tu es un assistant IA francophone polyvalent. Tu réponds de façon "
            "claire, structurée et concise. Tu distingues les faits vérifiables "
            "des hypothèses, tu signales ton incertitude et tu ne inventes jamais "
            "de source. Quand des sources sont fournies, appuie chaque affirmation "
            "importante sur l'une d'elles et cite-la sous la forme [Source N]."
        ),
    },
    {
        "slug": "informatique",
        "label": "Informatique",
        "icon": "⌘",
        "description": "Développement, sécurité, architecture et exploitation.",
        "system_prompt": (
            "Tu es un ingénieur logiciel senior spécialisé en développement web, "
            "sécurité et exploitation. Tu proposes des solutions concrètes, "
            "progressives et maintenables. Tu cites les bonnes pratiques et les "
            "sources fournies avec [Source N]. Tu rappelles les risques de sécurité "
            "et tu ne fournis jamais de secret réel. Pour les commandes destructrices, "
            "tu expliques les sauvegardes et les vérifications préalables."
        ),
    },
    {
        "slug": "finance",
        "label": "Finance",
        "icon": "◈",
        "description": "Analyse financière, budget, facturation et trésorerie.",
        "system_prompt": (
            "Tu es un analyste financier rigoureux. Tu expliques les notions, tu "
            "montres les calculs et tu précises les hypothèses. Tu cites les sources "
            "fournies avec [Source N]. Tu ne présentes pas une réponse comme un conseil "
            "d'investissement ou fiscal personnalisé : tu recommandes de faire valider "
            "les décisions par un professionnel. Tu attires l'attention sur les données "
            "manquantes et les risques."
        ),
    },
    {
        "slug": "data",
        "label": "Analyse de données",
        "icon": "▦",
        "description": "Qualité, gouvernance, exploration et anomalies.",
        "system_prompt": (
            "Tu es un expert en qualité et gouvernance des données. Tu raisonnes en "
            "dimensions : complétude, unicité, cohérence, validité, actualité et "
            "pertinence. Tu cites les sources fournies avec [Source N]. Tu distingues "
            "les anomalies statistiques des erreurs métier, tu expliques les limites "
            "des indicateurs et tu proposes des contrôles reproductibles. Tu ne conclus "
            "jamais à une conformité juridique complète à partir d'un simple profil de "
            "données."
        ),
    },
    {
        "slug": "education",
        "label": "École / Administration",
        "icon": "◫",
        "description": "Inscriptions, attestations, paiements et procédures.",
        "system_prompt": (
            "Tu es un assistant administratif d'établissement scolaire. Tu réponds en "
            "français, avec des étapes numérotées et les pièces nécessaires. Tu cites "
            "les procédures fournies avec [Source N]. Tu ne prétends jamais avoir "
            "inscrit un étudiant, délivré un document ou encaissé un paiement. Si une "
            "procédure manque, tu l'indiques et tu orientes vers le service compétent."
        ),
    },
    {
        "slug": "sante",
        "label": "Santé",
        "icon": "✚",
        "description": "Rendez-vous, confidentialité et parcours de soins.",
        "system_prompt": (
            "Tu es un assistant administratif de santé. Tu donnes des informations "
            "générales, jamais un diagnostic ni une prescription. Tu cites les sources "
            "fournies avec [Source N]. Tu rappelles la confidentialité, le consentement "
            "et la nécessité de consulter un professionnel en cas d'urgence ou de doute. "
            "Tu ne prétends pas avoir réservé un rendez-vous ou transmis un dossier."
        ),
    },
    {
        "slug": "droit",
        "label": "Droit",
        "icon": "§",
        "description": "Méthode juridique, contrats et protection des données.",
        "system_prompt": (
            "Tu es un assistant juridique documentaire. Tu présentes les notions, les "
            "textes et les points de vigilance, en citant les sources fournies avec "
            "[Source N]. Tu précises que ta réponse est informative et ne constitue pas "
            "une consultation juridique. Tu distingues le droit applicable, la "
            "jurisprudence et les clauses contractuelles."
        ),
    },
    {
        "slug": "marketing",
        "label": "Marketing",
        "icon": "◎",
        "description": "Segmentation, campagnes, mesure et consentement.",
        "system_prompt": (
            "Tu es un stratège marketing orienté données. Tu proposes des hypothèses "
            "testables, des indicateurs et des expérimentations mesurables. Tu cites les "
            "sources fournies avec [Source N]. Tu rappelles les règles de consentement, "
            "de transparence et de protection des données. Tu évites les promesses "
            "d'augmentation de revenus non étayées."
        ),
    },
]


SOURCES = [
    # ------------------------------------------------------------------ Général
    {
        "domain": "general",
        "title": "Méthode de réponse structurée",
        "kind": "document",
        "origin": "Guide interne",
        "content": (
            "Une réponse de qualité commence par une reformulation courte de la demande. "
            "Cette étape permet de vérifier que l'intention comprise correspond à la question posée. "
            "Elle évite de répondre à côté du sujet et donne à l'utilisateur la possibilité de corriger le tir.\n\n"
            "La réponse elle-même suit un ordre simple : constat, analyse, recommandation. "
            "Le constat rappelle les faits disponibles. L'analyse explique le raisonnement et les hypothèses. "
            "La recommandation propose une action concrète, priorisée et réalisable.\n\n"
            "Les affirmations importantes doivent être reliées à une source ou à un calcul vérifiable. "
            "Lorsque l'information manque, il faut l'écrire explicitement plutôt que de combler le vide par une supposition. "
            "Une réponse honnête sur ses limites est plus utile qu'une réponse faussement certaine.\n\n"
            "Enfin, la réponse se termine par les prochaines étapes : ce que l'utilisateur peut faire maintenant, "
            "les informations à réunir et les points à faire valider par un spécialiste si nécessaire."
        ),
    },
    {
        "domain": "general",
        "title": "Vérification et gestion de l'incertitude",
        "kind": "document",
        "origin": "Guide interne",
        "content": (
            "Toute information doit être datée et rattachée à son origine. "
            "Un chiffre sans période, un texte sans version ou une règle sans source ne peut pas être vérifié. "
            "Avant de réutiliser une information, il faut vérifier qu'elle est toujours applicable.\n\n"
            "Il faut distinguer trois niveaux : le fait observé, l'inférence raisonnable et l'hypothèse. "
            "Le fait est directement présent dans une source. L'inférence découle d'un raisonnement explicite. "
            "L'hypothèse est une possibilité non confirmée. Ces trois niveaux ne doivent pas être mélangés dans la même affirmation.\n\n"
            "Lorsque deux sources se contredisent, il faut signaler la contradiction, comparer leurs dates et leurs périmètres, "
            "puis privilégier la source la plus récente et la plus officielle. En l'absence d'arbitrage, la prudence consiste "
            "à présenter les deux versions et à indiquer ce qu'il reste à vérifier."
        ),
    },
    {
        "domain": "general",
        "title": "Confidentialité et bonnes pratiques de sécurité",
        "kind": "document",
        "origin": "Politique de sécurité",
        "content": (
            "Ne jamais saisir dans une conversation un mot de passe, une clé API, un numéro de carte bancaire "
            "ou un identifiant de sécurité social. Les outils de démonstration ne sont pas conçus pour conserver "
            "des secrets et les journaux peuvent en garder une trace.\n\n"
            "Les données personnelles doivent être minimisées : ne transmettre que les champs strictement nécessaires "
            "à la réponse. Les noms, adresses, courriels et numéros de téléphone doivent être retirés ou pseudonymisés "
            "lorsque le contexte le permet.\n\n"
            "Avant de partager un export, vérifier qu'il ne contient ni données sensibles ni informations internes. "
            "Un export de conversation est un document à protéger au même titre que la conversation elle-même."
        ),
    },
    # -------------------------------------------------------------- Informatique
    {
        "domain": "informatique",
        "title": "Sécurité des applications web",
        "kind": "document",
        "origin": "Référentiel technique",
        "content": (
            "Toute donnée reçue du navigateur est non fiable. Les entrées doivent être validées côté serveur : "
            "type attendu, longueur maximale, format et liste blanche lorsque c'est possible. "
            "La validation côté client améliore l'expérience mais ne remplace jamais la validation serveur.\n\n"
            "Les injections SQL se préviennent avec des requêtes paramétrées. Les attaques XSS se préviennent "
            "en échappant les sorties et en assainissant le HTML affiché. Les actions sensibles doivent être "
            "protégées contre le CSRF par un jeton et une vérification de l'origine. Les cookies de session "
            "doivent être HttpOnly, Secure et SameSite.\n\n"
            "Les secrets ne doivent pas être stockés dans le code ni dans un dépôt Git. Ils sont fournis par "
            "des variables d'environnement ou un coffre-fort de secrets, avec des droits limités et une rotation. "
            "Les dépendances doivent être verrouillées, mises à jour et surveillées pour les vulnérabilités connues.\n\n"
            "Enfin, les messages d'erreur destinés à l'utilisateur ne doivent pas révéler de pile d'appels, "
            "de chemin serveur, de requête SQL ou de secret. Les détails techniques vont dans les journaux, "
            "le message utilisateur reste clair et actionnable."
        ),
    },
    {
        "domain": "informatique",
        "title": "Déploiement, supervision et gestion d'incident",
        "kind": "document",
        "origin": "Référentiel technique",
        "content": (
            "Un déploiement fiable sépare les environnements de développement, de recette et de production. "
            "La configuration est injectée par l'environnement et non codée en dur. Les migrations de base de "
            "données sont versionnées et exécutées avant le nouveau code. Un mécanisme de retour arrière doit être "
            "préparé avant la mise en production.\n\n"
            "La supervision repose sur trois piliers : les journaux, les métriques et les traces. Les journaux "
            "doivent être structurés et corrélés par un identifiant de requête. Les métriques suivent la latence, "
            "le taux d'erreur, le débit et la saturation des ressources. Les traces relient les appels entre services.\n\n"
            "En cas d'incident, la priorité est de rétablir le service, puis de comprendre la cause. "
            "Un compte rendu factuel documente l'impact, la chronologie, la cause racine et les actions correctives. "
            "Les sauvegardes doivent être testées régulièrement : une sauvegarde non restaurée n'est pas une sauvegarde fiable."
        ),
    },
    {
        "domain": "informatique",
        "title": "RGPD et développement logiciel",
        "kind": "document",
        "origin": "Fiche conformité",
        "content": (
            "Le RGPD s'applique dès qu'un traitement porte sur des données personnelles, c'est-à-dire des données "
            "permettant d'identifier une personne directement ou indirectement. Le principe de minimisation impose "
            "de ne collecter que les données nécessaires à une finalité déterminée et explicite.\n\n"
            "Chaque traitement doit reposer sur une base légale : consentement, contrat, obligation légale, intérêt "
            "vital, mission d'intérêt public ou intérêt légitime. Le consentement doit être libre, spécifique, "
            "éclairé et révocable aussi facilement qu'il a été donné.\n\n"
            "Les personnes disposent de droits d'accès, de rectification, d'effacement, de limitation, d'opposition "
            "et de portabilité. Les demandes doivent être traitées dans les délais prévus. Les données doivent être "
            "conservées pour une durée limitée et les accès doivent être restreints au strict nécessaire.\n\n"
            "La sécurité fait partie des obligations : chiffrement lorsque c'est pertinent, contrôle d'accès, "
            "journalisation, sauvegardes et procédure de notification des violations. Un sous-traitant doit offrir "
            "des garanties suffisantes et être encadré par un contrat conforme."
        ),
    },
    # ------------------------------------------------------------------- Finance
    {
        "domain": "finance",
        "title": "Lecture des états financiers",
        "kind": "document",
        "origin": "Support de formation",
        "content": (
            "Le compte de résultat mesure la performance sur une période : produits, charges et résultat. "
            "Le bilan photographie le patrimoine à une date donnée : actifs, passifs et capitaux propres. "
            "Le tableau de trésorerie explique les variations de liquidités sur la période.\n\n"
            "Les ratios doivent être interprétés ensemble. La marge nette rapporte le résultat au chiffre d'affaires. "
            "Le ratio de liquidité générale compare les actifs circulants aux dettes à court terme. "
            "Le taux d'endettement rapporte les dettes aux capitaux propres. Un ratio isolé ne suffit pas à conclure.\n\n"
            "Il faut comparer les ratios dans le temps, avec le secteur et avec les objectifs de l'entreprise. "
            "Les changements de méthode comptable, les opérations exceptionnelles et la saisonnalité peuvent fausser "
            "la comparaison. Les données doivent être retraitées avant toute conclusion."
        ),
    },
    {
        "domain": "finance",
        "title": "TVA, facturation et recouvrement",
        "kind": "document",
        "origin": "Fiche pratique",
        "content": (
            "Une facture doit être datée, numérotée de façon unique et séquentielle, et identifier clairement le "
            "vendeur et le client. Elle précise la nature des biens ou services, les quantités, les prix unitaires, "
            "les taux de TVA appliqués et le total à payer. Les mentions obligatoires dépendent du pays et du régime.\n\n"
            "La TVA collectée n'est pas un revenu : elle est reversée à l'administration après déduction de la TVA "
            "déductible. Une erreur de taux ou de base imposable doit être corrigée par une facture rectificative, "
            "jamais par une modification silencieuse de la facture initiale.\n\n"
            "Le recouvrement commence par des conditions de paiement claires et un suivi des échéances. "
            "Les relances doivent être datées, graduées et documentées. Une créance ancienne doit être provisionnée "
            "ou passée en perte selon la politique comptable. Le contentieux est un dernier recours."
        ),
    },
    {
        "domain": "finance",
        "title": "Budget, écarts et trésorerie",
        "kind": "document",
        "origin": "Fiche pratique",
        "content": (
            "Un budget est une prévision chiffrée et datée des produits et des charges. Il se construit à partir "
            "d'hypothèses explicites : volumes, prix, taux de change, inflation, effectifs. Chaque hypothèse doit "
            "être documentée et révisable.\n\n"
            "Le suivi budgétaire compare le réalisé au prévu. L'écart se décompose en effet volume, effet prix et "
            "effet mix. Il faut analyser les écarts significatifs, pas seulement les écarts défavorables. "
            "Un écart favorable peut masquer un problème de qualité ou un report de charge.\n\n"
            "La trésorerie se pilote à part du résultat. Une entreprise rentable peut manquer de liquidités si ses "
            "clients paient tard ou si elle investit massivement. Le prévisionnel de trésorerie doit intégrer les "
            "décalages d'encaissement, les échéances de dette et un coussin de sécurité. Des scénarios pessimiste, "
            "central et optimiste permettent d'anticiper les tensions."
        ),
    },
    # -------------------------------------------------------------- Data
    {
        "domain": "data",
        "title": "Les dimensions de la qualité des données",
        "kind": "document",
        "origin": "Référentiel data",
        "content": (
            "La complétude mesure la proportion de valeurs renseignées. Elle se calcule par colonne et globalement. "
            "Une donnée absente peut être légitime, inconnue ou perdue : le taux seul ne dit pas laquelle des trois "
            "situations s'applique. Il faut donc qualifier la cause des manquants.\n\n"
            "L'unicité vérifie l'absence de doublons. Un doublon peut porter sur une ligne entière ou sur une clé "
            "métier. Deux lignes différentes peuvent représenter la même entité : c'est un doublon fonctionnel. "
            "La détection nécessite une règle de rapprochement explicite.\n\n"
            "La cohérence contrôle le respect des règles internes : formats, unités, relations entre colonnes, "
            "référentiels. La validité contrôle le respect des formats et des domaines autorisés, par exemple une "
            "adresse électronique valide ou une date réelle. L'actualité mesure la fraîcheur par rapport à l'usage prévu.\n\n"
            "Un indicateur de qualité n'a de sens que relié à un usage. Un taux de complétude de 95 % peut être "
            "insuffisant pour un calcul financier et suffisant pour une tendance exploratoire. Les seuils doivent "
            "être définis avec les propriétaires métier."
        ),
    },
    {
        "domain": "data",
        "title": "Gouvernance des données",
        "kind": "document",
        "origin": "Référentiel data",
        "content": (
            "La gouvernance des données définit qui est responsable de quoi. Un propriétaire métier répond de la "
            "définition et de l'usage de la donnée. Un intendant data assure la qualité au quotidien. Un administrateur "
            "gère les accès et l'infrastructure. Les responsabilités doivent être nommées et documentées.\n\n"
            "Un catalogue de données décrit les jeux de données, leurs colonnes, leur sens, leur source, leur "
            "fréquence de mise à jour et leurs règles de qualité. Le lignage retrace les transformations depuis la "
            "source jusqu'à l'usage final. Il permet d'évaluer l'impact d'un changement et d'identifier l'origine d'une erreur.\n\n"
            "La politique d'accès applique le moindre privilège : chaque utilisateur n'accède qu'aux données "
            "nécessaires à sa mission. Les données sensibles sont classifiées, chiffrées et journalisées. "
            "Le cycle de vie prévoit la création, la modification, l'archivage et la suppression.\n\n"
            "Enfin, la gouvernance produit des preuves : décisions, contrôles, incidents, actions correctives. "
            "Sans traçabilité, la conformité reste déclarative et difficile à démontrer."
        ),
    },
    {
        "domain": "data",
        "title": "Détection des anomalies et valeurs extrêmes",
        "kind": "document",
        "origin": "Guide analytique",
        "content": (
            "Une anomalie est une observation qui s'écarte du comportement attendu. Elle n'est pas nécessairement "
            "une erreur : un pic de ventes peut être légitime. L'analyse doit combiner la détection statistique et "
            "la connaissance métier avant de conclure.\n\n"
            "La méthode de l'écart interquartile (IQR) est robuste aux valeurs extrêmes. On calcule le premier "
            "quartile Q1, le troisième quartile Q3 et l'écart IQR = Q3 - Q1. Les valeurs inférieures à Q1 - 1,5 × IQR "
            "ou supérieures à Q3 + 1,5 × IQR sont signalées comme atypiques. Pour une distribution très asymétrique, "
            "une transformation logarithmique ou une méthode par quantiles peut être préférable.\n\n"
            "Les doublons se détectent sur la ligne complète ou sur une clé. Les incohérences apparaissent quand "
            "deux colonnes se contredisent, par exemple une date de fin antérieure à la date de début. "
            "Les valeurs manquantes doivent être distinguées des valeurs vides, nulles ou sentinelles comme -1 ou 9999.\n\n"
            "Chaque contrôle devrait produire un indicateur, un seuil, une liste d'exemples et une action attendue. "
            "Un contrôle sans propriétaire ni seuil ne sera pas suivi dans le temps."
        ),
    },
    # -------------------------------------------------------------- Éducation
    {
        "domain": "education",
        "title": "Inscriptions et pièces justificatives",
        "kind": "document",
        "origin": "Procédure établissement",
        "content": (
            "L'inscription administrative comporte généralement la création ou la mise à jour du dossier étudiant, "
            "la vérification de l'identité, le dépôt des pièces justificatives et la validation du dossier par le "
            "service compétent. Une demande déposée n'est pas une inscription confirmée.\n\n"
            "Les pièces demandées peuvent inclure une pièce d'identité, un justificatif de domicile, le dernier "
            "diplôme obtenu, une photo et, selon le cas, un justificatif de financement ou de bourse. "
            "La liste exacte dépend du programme et de l'année universitaire.\n\n"
            "Le suivi se fait par un identifiant de dossier. L'étudiant peut vérifier l'état de sa demande : "
            "déposée, incomplète, en cours d'instruction, validée ou refusée. Une pièce manquante doit être signalée "
            "avec un délai de régularisation. Les données personnelles du dossier sont confidentielles."
        ),
    },
    {
        "domain": "education",
        "title": "Attestations et relevés de notes",
        "kind": "document",
        "origin": "Procédure établissement",
        "content": (
            "Une attestation de scolarité prouve l'inscription pour une année donnée. Elle est délivrée après "
            "validation administrative et peut être téléchargée depuis l'espace étudiant ou demandée au secrétariat. "
            "Elle ne remplace pas un diplôme ni un relevé de notes officiel.\n\n"
            "Un relevé de notes présente les enseignements suivis, les crédits, les notes et les résultats. "
            "Une attestation de réussite est délivrée après délibération du jury. Les notes provisoires ne doivent "
            "pas être présentées comme définitives.\n\n"
            "En cas d'erreur, l'étudiant dépose une demande de rectification avec les pièces justificatives. "
            "La demande est instruite par le service des examens. Un document officiel ne doit jamais être modifié "
            "manuellement : il est réédité après validation."
        ),
    },
    {
        "domain": "education",
        "title": "Paiements, échéanciers et remboursements",
        "kind": "document",
        "origin": "Procédure établissement",
        "content": (
            "Les frais de scolarité peuvent être réglés en une ou plusieurs fois selon l'échéancier autorisé. "
            "Chaque paiement donne lieu à un justificatif. Un échéancier accepté ne vaut pas renonciation aux "
            "conditions générales et doit être respecté aux dates convenues.\n\n"
            "Une demande de remboursement doit être motivée et accompagnée des justificatifs. Elle est examinée "
            "par le service financier au regard des conditions d'annulation ou de désinscription. Un remboursement "
            "nécessite une validation humaine : l'assistant ne peut ni l'approuver ni le promettre.\n\n"
            "En cas de difficulté de paiement, l'étudiant doit contacter le service avant l'échéance pour étudier "
            "un aménagement. Le non-paiement peut entraîner une suspension administrative ou une exclusion des examens "
            "selon le règlement applicable."
        ),
    },
    # ------------------------------------------------------------------ Santé
    {
        "domain": "sante",
        "title": "Confidentialité et consentement",
        "kind": "document",
        "origin": "Fiche santé",
        "content": (
            "Les informations de santé sont des données personnelles sensibles. Leur collecte et leur transmission "
            "sont encadrées par le secret professionnel et par la réglementation sur la protection des données. "
            "Seules les personnes intervenant dans la prise en charge doivent y accéder.\n\n"
            "Le consentement du patient est requis pour de nombreux usages, notamment le partage avec un autre "
            "professionnel, la recherche ou l'utilisation de certaines applications. Le consentement doit être "
            "éclairé, spécifique et révocable. En cas d'urgence vitale, des exceptions peuvent s'appliquer.\n\n"
            "Les échanges par messagerie non sécurisée doivent être évités. Un document contenant des données de "
            "santé ne doit pas être envoyé à une adresse erronée. En cas de violation de données, une procédure "
            "d'alerte et de notification doit être déclenchée."
        ),
    },
    {
        "domain": "sante",
        "title": "Prise de rendez-vous et parcours de soins",
        "kind": "document",
        "origin": "Fiche santé",
        "content": (
            "Une demande de rendez-vous ne constitue pas une réservation tant qu'elle n'a pas été confirmée par le "
            "secrétariat ou le professionnel. L'utilisateur doit vérifier la date, l'heure, le lieu et le motif "
            "avant de se déplacer.\n\n"
            "En cas d'urgence vitale, il faut contacter immédiatement les services d'urgence compétents plutôt que "
            "d'utiliser un formulaire en ligne. Les symptômes ne doivent pas être détaillés dans un outil non sécurisé.\n\n"
            "L'annulation doit respecter les délais indiqués par le praticien. Un rendez-vous non honoré et non annulé "
            "peut être facturé selon les conditions prévues. Les données de rendez-vous sont conservées pour la durée "
            "nécessaire au suivi administratif et médical."
        ),
    },
    {
        "domain": "sante",
        "title": "Facturation et remboursement des soins",
        "kind": "document",
        "origin": "Fiche santé",
        "content": (
            "Une facture de soins identifie l'acte, la date, le professionnel et le montant. Selon le régime "
            "d'assurance maladie, une partie peut être prise en charge. Le patient doit vérifier les informations "
            "avant de transmettre sa facture à son organisme.\n\n"
            "Un remboursement dépend des règles applicables, de la couverture et des justificatifs fournis. "
            "Il ne peut pas être garanti avant instruction du dossier. L'assistant peut expliquer la procédure "
            "mais ne peut pas valider un remboursement.\n\n"
            "Les données bancaires et de santé doivent être transmises par un canal sécurisé. En cas d'erreur de "
            "facturation, il faut demander une facture rectificative et conserver les échanges."
        ),
    },
    # ------------------------------------------------------------------- Droit
    {
        "domain": "droit",
        "title": "Méthode d'analyse d'une question juridique",
        "kind": "document",
        "origin": "Méthode juridique",
        "content": (
            "Une analyse juridique commence par qualifier les faits : qui, quoi, quand, où, comment. "
            "Elle identifie ensuite la branche du droit concernée et les textes applicables. "
            "La qualification des faits détermine les règles pertinentes.\n\n"
            "Il faut distinguer les sources : constitution, traités, loi, règlement, jurisprudence, doctrine, "
            "contrat. Leur valeur et leur portée diffèrent. Une décision isolée ne crée pas nécessairement une règle "
            "générale. La date d'entrée en vigueur et les dispositions transitoires doivent être vérifiées.\n\n"
            "La réponse présente les arguments favorables et défavorables, les incertitudes et les risques. "
            "Elle ne se substitue pas à la consultation d'un avocat. Pour une décision importante, il faut produire "
            "les pièces, vérifier la compétence juridictionnelle et respecter les délais de prescription."
        ),
    },
    {
        "domain": "droit",
        "title": "Protection des données personnelles",
        "kind": "document",
        "origin": "Fiche conformité",
        "content": (
            "Le traitement de données personnelles doit reposer sur une base légale et poursuivre une finalité "
            "déterminée, explicite et légitime. Les données collectées doivent être adéquates, pertinentes et "
            "limitées au nécessaire.\n\n"
            "Les personnes doivent être informées de manière concise, transparente et compréhensible : responsable "
            "du traitement, finalités, base légale, destinataires, durées de conservation et droits. "
            "Les droits d'accès, de rectification, d'effacement, de limitation, d'opposition et de portabilité "
            "doivent pouvoir être exercés facilement.\n\n"
            "La sécurité technique et organisationnelle est obligatoire. Les violations de données doivent être "
            "documentées et, lorsqu'elles présentent un risque, notifiées à l'autorité compétente. "
            "Les transferts hors de l'Union européenne nécessitent des garanties appropriées.\n\n"
            "Un registre des activités de traitement aide à démontrer la conformité. Il doit être mis à jour à "
            "chaque évolution significative."
        ),
    },
    {
        "domain": "droit",
        "title": "Contrats : clauses à vérifier",
        "kind": "document",
        "origin": "Méthode juridique",
        "content": (
            "Avant de signer un contrat, il faut identifier les parties, l'objet, le prix, la durée et les "
            "conditions de renouvellement ou de résiliation. Les annexes et les documents référencés font partie "
            "du contrat et doivent être lus.\n\n"
            "Les clauses sensibles concernent la responsabilité, les pénalités, la confidentialité, la propriété "
            "intellectuelle, la protection des données, la sous-traitance, la force majeure et le règlement des "
            "litiges. Une clause de renouvellement tacite doit être repérée avant l'échéance.\n\n"
            "Le droit applicable et la juridiction compétente déterminent les recours possibles. "
            "Les engagements doivent être réalisables et mesurables. Une clause floue est une source de conflit. "
            "Pour un contrat important, une relecture par un professionnel est recommandée."
        ),
    },
    # --------------------------------------------------------------- Marketing
    {
        "domain": "marketing",
        "title": "Segmentation et personas",
        "kind": "document",
        "origin": "Guide marketing",
        "content": (
            "Une segmentation pertinente regroupe des clients qui partagent des besoins, des comportements ou des "
            "caractéristiques utiles pour l'action. Elle doit être mesurable, accessible, suffisamment grande et "
            "actionnable. Une segmentation purement démographique passe souvent à côté des motivations réelles.\n\n"
            "Un persona est une représentation synthétique d'un segment, fondée sur des données qualitatives et "
            "quantitatives. Il décrit les objectifs, les freins, les canaux et le parcours de décision. "
            "Il ne doit pas devenir une caricature ni remplacer les données réelles.\n\n"
            "La segmentation doit être réévaluée régulièrement : les comportements évoluent et les segments "
            "peuvent se diluer. Les critères de succès sont définis avant le lancement de la campagne."
        ),
    },
    {
        "domain": "marketing",
        "title": "Mesure de la performance marketing",
        "kind": "document",
        "origin": "Guide marketing",
        "content": (
            "Un indicateur marketing doit être relié à un objectif. Le taux de clic mesure l'intérêt pour un message, "
            "pas nécessairement la qualité de l'audience. Le coût d'acquisition rapporte les dépenses au nombre de "
            "clients acquis. La valeur vie client permet de comparer le coût d'acquisition à la valeur générée.\n\n"
            "Les tests A/B comparent une seule variable à la fois et nécessitent une taille d'échantillon suffisante. "
            "Il faut définir l'indicateur principal avant le test et éviter de multiplier les comparaisons jusqu'à "
            "trouver un résultat significatif. La signification statistique ne garantit pas l'importance métier.\n\n"
            "Les attributions multi-touch aident à comprendre le rôle des différents canaux, mais aucun modèle "
            "d'attribution n'est parfait. Les données doivent être consolidées avec les ventes réelles et le coût complet."
        ),
    },
    {
        "domain": "marketing",
        "title": "Consentement, éthique et conformité",
        "kind": "document",
        "origin": "Fiche conformité",
        "content": (
            "La prospection par courrier électronique et l'utilisation de cookies sont encadrées. Le consentement "
            "doit être préalable, libre, spécifique, éclairé et facile à retirer. Une case précochée ne constitue pas "
            "un consentement valable.\n\n"
            "Les messages doivent identifier clairement l'expéditeur et permettre de se désinscrire facilement. "
            "Les données collectées doivent être minimisées et conservées pour une durée limitée. "
            "Les audiences construites à partir de données sensibles nécessitent une vigilance renforcée.\n\n"
            "Les allégations publicitaires doivent être véridiques et vérifiables. Les comparaisons doivent être "
            "loyales. Les témoignages et les résultats présentés doivent être représentatifs et ne pas induire en erreur. "
            "Une campagne conforme protège la marque autant qu'elle protège les personnes."
        ),
    },
]
