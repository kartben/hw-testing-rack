# Revue des cinq cartes, 2026-11-09

Revue de conception du hub d'alimentation, du nœud de baie, de la carte caméra, de la DATA ×4 et de la DATA ×6, faite sur `main` au commit `c9d0926`, sans modification des fichiers de conception.  Elle cherche ce que l'ERC et le DRC ne voient pas : brochages, valeurs, tensions maximales, états par défaut, thermique, fichiers de fabrication.

**65 constats** : 0 critique, 4 majeurs, 37 mineurs, 24 remarques.  Aucune carte n'est fabriquée : rien n'a été mesuré.  Les températures, les transitoires et les effets de couplage sont calculés ; chaque constat dit s'il est confirmé sur pièces, probable ou à vérifier.

Préfixes des constats : `PH` hub d'alimentation · `BN` nœud de baie · `CP` carte caméra · `X4A` DATA ×4, base · `X4B` DATA ×4, logique · `X6` DATA ×6 · `SYS` ensemble du rack.

## Synthèse

**Aucune erreur de brochage, de polarité ni de connexion sur les cinq cartes**, et aucun constat critique. Les schémas sont justes ; ce qui reste tient aux fichiers de fabrication, à quelques états transitoires et à la thermique. Quatre constats majeurs, dont trois se règlent sans reroutage. Le hub d'alimentation et la carte caméra peuvent partir en fabrication ; le nœud, la DATA ×6 et la DATA ×4 demandent chacun une correction ou une décision avant commande.

**Dans l'ordre :**

1. **DATA ×6, fichier de placement :** ajouter la rotation de 270° du TCA9535 (X6-01). Sans elle, aucun port ne s'allume sur les cartes assemblées. Une ligne dans `build_board.py`.
2. **Nœud :** 1 kΩ en série sur IO40 (BN-01). En mode téléchargement, la ROM de l'ESP32 force cette broche à l'état haut contre la sortie de défaut de l'eFuse, au-delà de sa limite absolue.
3. **DATA ×6, régulateur 3,3 V :** lui donner du cuivre et des vias comme sur la DATA ×4 (X6-02) ; c'est le seul des quatre majeurs qui demande de retoucher le routage. Profiter du passage pour ramener le 5 V à 5,08 V (X6-07).
4. **Approvisionnement :** l'interrupteur de port TPS2553DBVR-1 des deux cartes DATA est épuisé chez JLC (SYS-6). Attendre, fournir la pièce, ou changer de référence et confier le verrouillage au micrologiciel.
5. **Une décision à prendre :** la limite de courant du cordon DATA (SYS-1), aujourd'hui au-dessus de celle de la rangée et de la pleine échelle de mesure.
6. **Fichiers de placement, encore :** la diode DFLS260 du nœud et du hub est décalée de 0,34 mm (BN-06, PH-01, une même ligne à ajouter). Dans l'aperçu JLC, contrôler le sens de l'inductance du RP2350B (X4B-05), la polarité de C60 et l'orientation des embases USB-C (X6-11).
7. **DATA ×4, tant que le routage est ouvert :** éloigner le cuivre du hub de la broche 28 V soudée à la main (X4A-01), donner du cuivre à l'abaisseur et le mesurer à pleine charge (X4A-02), ajouter des vias de masse sous le RP2350B (X4B-03).
8. **Nœud et hub, tant qu'on y touche :** 10 Ω sur les entrées de l'INA226 (BN-02), éloigner la ligne de la LED d'état de la paire USB (BN-05), épaissir le retour de masse du connecteur PD (PH-02).
9. **Règles d'usage à écrire :** ne pas brancher le cordon DATA sous tension (X6-04), couper la rangée avant d'y ajouter un nœud (BN-04).
10. **Documentation :** elle décrit encore l'ancienne alimentation 5 V, promet un mode classique sans micrologiciel qui n'existe plus, et verrouille le 28 V pour une raison qui a disparu (SYS-2, BN-07).

Rien n'a été mesuré : aucune carte n'est fabriquée. Les températures, les transitoires et les effets de couplage sont calculés ; chaque constat dit s'il est confirmé sur pièces, probable ou à vérifier.

## Verdict par carte

| Carte | Verdict | Majeurs | Mineurs | Remarques |
|---|---|---|---|---|
| Hub d'alimentation (`power-hub v1.0`) | Bonne pour fabrication en 20 V, retouches mineures conseillées | 0 | 6 | 6 |
| Nœud de baie (`bay-node v1.0`) | À corriger avant commande : 1 constat majeur | 1 | 7 | 4 |
| Carte caméra (`camera-pod v1.0`) | Bonne pour fabrication, retouches mineures | 0 | 2 | 1 |
| DATA ×4 (`data-port-x4 v1.0`) | Pas de constat majeur propre à la carte ; commande bloquée par un stock | 0 | 11 | 8 |
| DATA ×6 (`data-port-x6 v1.0`) | À corriger avant commande : 2 constats majeurs | 2 | 8 | 3 |
| Ensemble du rack | Une rupture de stock, une décision à prendre | 1 | 3 | 2 |

## Avant l'envoi à NextPCB

Le tri fait avec le propriétaire le 2026-11-10, pour une commande chez NextPCB avec un fichier de positions KiCad brut.

**À corriger avant envoi (deux corrections matérielles)**

1. **Nœud, BN-01 :** 1 kΩ en série entre `DUT_FLT_N` (`U9.14`, `R18`) et `U3.33` (IO40).  Repli sans retouche : brûler l'eFuse `DIS_USB_OTG_DOWNLOAD_MODE`, mais le premier flashage de chaque carte subit quand même la surcharge.
2. **DATA ×6, X6-02 :** cuivre et vias sous la languette du régulateur 3,3 V `U3`, comme sur la DATA ×4 (zones `ldo-vout` et `ldo-back`, quinze vias).

**Changements de valeur à faire dans la même passe**

- **DATA ×6, X6-07 :** `R53` et `R55` à 18,7 kΩ (5,08 V au lieu de 5,24 V).  La ligne 18 kΩ de la nomenclature devient 18,7 kΩ.
- **Nœud, SYS-1 :** `R16` à 8,2 kΩ si la limite du cordon DATA doit passer sous celle de la rangée (arbitrage du propriétaire).  La ligne 6,8 kΩ devient 8,2 kΩ.

**DATA ×4 : vias de masse sous le RP2350B (X4B-03), retenu le 2026-11-10**

Vias de 0,5 / 0,3 mm aux croisements des fenêtres de pâte de la pastille centrale de `U11`, mesurés sur le PCB routé :

| Position | État | Cuivre voisin sur B.Cu |
|---|---|---|
| (47,565 ; 13,465) | via existant | |
| (46,435 ; 12,335) | libre | `BUS_B` à 0,31 mm : passe sans rien déplacer |
| (46,435 ; 13,465) | libre, au plancher des règles | `BUS_A` à 0,108 mm pour 0,1 mm exigé ; à confirmer par le DRC |
| (47,565 ; 12,335) | occupé | chevauche `BUS_B` : il faut décaler cette piste |

Dans `electronics/data-port-x4/design.py`, vers la ligne 1710, `hand_vias` ne contient que `(ux + 0.565, uy + 0.565)` : y ajouter les positions à x = `ux − 0.565`.  Le PCB routé ne se régénère pas (cela relancerait tout le routage) : les vias s'ajoutent dans le `.kicad_pcb`, puis `tools/kicad.sh data-port-x4 --check --fab` et `tools/panel.sh data-port-x4`.

**Fichiers à envoyer, sans toucher aux cartes**

- Le fichier de positions KiCad brut pour chaque carte, jamais les `fab/*-cpl-jlcpcb.csv` (voir SYS-7).  Celui de la DATA ×6 a été contrôlé : ses 158 lignes sont celles du PCB.
- Le devis des deux cartes DATA au palier 3,5 / 3,5 mil.
- Dans l'aperçu de placement : le point de `U2` (DATA ×6), le « + » de `C60`, le sens des embases USB-C, le point de l'inductance `L1` du RP2350B (DATA ×4 logique).

**Seulement si le routage d'une carte est rouvert**

- Nœud : 10 Ω sur les entrées de l'INA226 (BN-02), `LED_DIN` éloignée de la paire USB (BN-05).
- DATA ×4 : cuivre dégagé autour de la broche 28 V soudée à la main (X4A-01).
- DATA ×4 et ×6 : trous de centrage des embases USB-C au plan GCT actuel (X6-09) ; si une embase ne descend pas à plat, il n'y a pas de rattrapage.
- Hub : retour de masse du connecteur PD (PH-02), piste sous l'entretoise (PH-03).

**Ne s'appliquent pas chez NextPCB :** X6-01 (rotation du TCA9535), BN-06 et PH-01 (décalage des diodes), PH-10 (empreinte JLC de l'inductance).  SYS-6 (stock du TPS2553DBVR-1) tombe probablement aussi, selon la source d'approvisionnement de l'assembleur.

**Effet sur les devis.**  Dimensions, couches, finition, palier et quantités ne changent pas.  Nomenclature : une résistance de 1 kΩ de plus par nœud sur une ligne existante ; les deux changements de valeur remplacent chacun une ligne par une autre.  La règle de NextPCB sur un renvoi de fichiers n'a pas été vérifiée.

## Constats, par ordre d'importance

« Connu » signale un point déjà noté dans la documentation du dépôt.  Confiance : *confirmé* (vérifié sur le PCB, la conception et les fiches), *probable*, *à vérifier*.

### Majeurs (4)

#### X6-01 · DATA ×6 · Le TCA9535 n'a pas de correction de rotation : le fichier de placement le pose tourné de 90°

*Majeur · confirmé*

- **Où :** `U2` (TCA9535RTWR, C129354) · `fab/data-port-x6-cpl-jlcpcb.csv` : `U2 … Top, 0` · `build_board.py`, table `JLC_CPL_FIX` : aucune entrée C129354
- **Constat :** L'empreinte JLC de cette référence a sa pastille 1 à gauche de la rangée du bas (−1,25 ; +1,908). Celle de KiCad l'a en haut de la colonne de gauche (−1,938 ; −1,25). Il faut donc 270° de correction, comme pour le TCA6408A (C181499), qui a le même dessin et figure déjà dans la table. Le TCA9535 est nouveau sur cette carte et n'y a pas été ajouté. Vérifié sur les deux empreintes et sur le fichier de placement. **Ce constat ne vaut que pour le fichier corrigé pour JLC** (`-cpl-jlcpcb.csv`). Un fichier de positions KiCad brut, où U2 est à 0°, est cohérent avec les Gerbers : broche 1 en haut à gauche, là où la sérigraphie met sa flèche.
- **Conséquence :** Posé comme le fichier le dit, chaque broche arrive six pastilles plus loin : VCC sur une pastille tirée à la masse, pas de réponse à 0x20, toutes les commandes EN restent à l'état bas. **Aucun port ne peut être allumé, sur toutes les cartes assemblées**, jusqu'à ce que U2 soit levé et tourné à l'air chaud. Sans destruction. Le contrôle de JLC rattrape souvent un QFN d'après le point de sérigraphie, mais la règle du projet est de ne pas compter dessus.
- **Correction :** Ajouter `"C129354": ("WQFN-24-1EP_4x4mm_P0.5mm_EP2.45x2.45mm", 270, 0.0, 0.0)` à `JLC_CPL_FIX`, régénérer le fichier de placement, et vérifier le point de U2 dans l'aperçu JLC.

#### BN-01 · Nœud · En mode téléchargement, l'ESP32 force IO40 à l'état haut contre la sortie de défaut de l'eFuse, qui est à l'état bas

*Majeur · confirmé*

- **Où :** `DUT_FLT_N` : `U9.14` (~FLT), `R18` (10 kΩ vers +3V3), `U3.33` (IO40), sans pièce en série · `design.py:649`, `:795–797`
- **Constat :** Le guide de conception d'Espressif indique que la ROM, en mode de téléchargement USB-OTG, met MTDO (IO40) en sortie à l'état haut. La fiche du TPS2660 indique que ~FLT est tiré à la masse dès que le circuit est en arrêt avec SHDN bas, ce qui est l'état par défaut ici (`R17`). Les deux se rencontrent à chaque session de flashage par la ROM : 3,3 V / (85 Ω + ≈ 30 Ω) ≈ 28 mA, 17 mA au mieux, pour 10 mA maximum absolu sur ~FLT. La doc du dépôt traite encore ce cas pour l'ancien TPS2553, où il ne se produisait qu'en cas de défaut. Vérifié sur le PCB et dans les deux fiches, non mesuré.
- **Conséquence :** La sortie de défaut de l'eFuse est sollicitée deux à trois fois au-delà de sa limite pendant tout le premier flashage de chaque carte, et à chaque flashage tant que l'eFuse `DIS_USB_OTG_DOWNLOAD_MODE` n'est pas brûlé. Une sortie ~FLT dégradée bloque ensuite la mise sous tension du cordon DATA par le micrologiciel.
- **Correction :** 1 kΩ en série entre `DUT_FLT_N` et `U3.33` (valeur déjà sur la carte) : 3 mA au pire, sans effet sur le niveau logique. Ou déplacer DUT_FLT_N sur une broche libre (IO5, IO6, IO8). Sur des cartes déjà fabriquées : brûler l'eFuse au premier flashage et couper la piste si besoin.

#### X6-02 · DATA ×6 · Le régulateur 3,3 V n'a aucun cuivre pour se refroidir

*Majeur · probable*

- **Où :** `U3` (AP2114H-3.3, SOT-223) à (68,8 ; 4,6) · languette : une piste de 0,25 × 1,35 mm vers un via · aucune zone +3V3 sur F.Cu ni B.Cu
- **Constat :** La languette n'a qu'une liaison : une piste fine vers un seul via de 0,5 / 0,3 mm dans le plan interne. La feuille de schéma annonce pourtant « SOT-223 on copper ». La DATA ×4 a reçu pour le même régulateur deux îlots (49 et 28 mm²) et quinze vias ; ce correctif n'a pas été reporté ici. Le hub tire 205–235 mA avec un hôte à pleine vitesse (l'ESP32 du nœud) et 330 à 460 mA avec un hôte à haute vitesse. Depuis 5,24 V : 0,47 W, puis 0,65 à 0,97 W. Avec les 128 °C/W de la fiche Diodes sans dissipateur et 40 °C d'air : ≈ 100 °C, puis 123 à 164 °C. Le cuivre est vérifié sur le PCB ; les températures sont calculées.
- **Conséquence :** Correct avec l'ESP32 comme hôte. En mode classique, un ordinateur et quatre périphériques haute vitesse ou plus amènent le régulateur vers sa coupure thermique (160 °C) dans un tiroir fermé : le 3,3 V tombe, le hub redémarre, tous les périphériques se réénumèrent, en boucle.
- **Correction :** Comme sur la DATA ×4 : un îlot +3V3 côté composants autour de la languette, englobant la pastille de `C3`, un îlot en regard sur la face arrière, six vias ou plus. Sans reroutage : ≈ 2,2 Ω en série avec l'entrée de U3 pour sortir la moitié de la dissipation du boîtier. Mesurer la languette, tiroir fermé, avec six périphériques haute vitesse.

#### SYS-6 · Ensemble · L'interrupteur de port TPS2553DBVR-1 est épuisé chez JLC : 1 pièce en stock

*Majeur · confirmé*

- **Où :** C111738 · DATA ×6 `U101–U601` (6 par carte) · DATA ×4 `U101–U401` (4 par carte)
- **Constat :** Consultation en direct du catalogue JLC le 9 novembre 2026 : 1 pièce. L'instantané du dépôt, daté du 4 novembre, en comptait 196. Les remplaçants au même brochage, TPS2553DBVR (C55266, ≈ 57 000 en stock) et TPS2553DDBVR (C521201), **ne se verrouillent pas** sur défaut. La version verrouillable existe en WSON-6 (C411878), une autre empreinte. Ce n'est pas un défaut de conception, mais la commande ne peut pas partir telle quelle. La rupture est propre au catalogue JLC : Mouser en affichait 8 334 le 9 novembre 2026 (DigiKey non consulté).
- **Conséquence :** Avec un remplaçant non verrouillable, un port en court-circuit reste en limitation (≈ 2,9 W dans un SOT-23-6) et cycle thermiquement jusqu'à ce que le nœud coupe EN ; le signal de défaut se relâche tout seul. Les notes de conception s'appuient sur le verrouillage (« a port's fault needs no node »).
- **Correction :** À décider avant de commander : attendre ou fournir soi-même C111738 (stock Mouser et DigiKey non consulté), ou monter C55266 et confier le verrouillage au micrologiciel (EN à l'état bas dès la première lecture d'un défaut). L'inductance IHLP2525CZ (C48009678) est passée de 5 690 à 690 pièces en cinq jours : surveiller aussi.

### Mineurs (37)

#### PH-02 · Hub · Le retour de masse du connecteur d'entrée PD est mince face à son côté VBUS

*Mineur · confirmé*

- **Où :** `J1`, pastilles GND A12/B1 (x = 58,8) et A1/B12 (x = 65,2) · `design.py:211`, `:319`, `:323`
- **Constat :** Le côté VBUS est taillé pour 5 A : une zone pleine et cinq vias de 0,8 / 0,4 mm. Le retour ne l'est pas. Les deux pastilles de masse de gauche sont enfermées dans le contour de la zone VBUS, donc la zone de masse ne les atteint pas : leur seul cuivre est une piste de 0,3 mm vers un via de 0,5 / 0,3 mm. Celles de droite ont une piste de 0,25 mm vers la patte du blindage et deux pistes de 0,2 mm vers deux petits vias. Vérifié sur le PCB.
- **Conséquence :** Cela fonctionne : le rétrécissement est court et chauffe peu. Mais le retour de tout le rack, jusqu'à 2,5 A par paire de contacts, dépend d'un petit via et d'une piste fine, à l'inverse de la règle de la carte (« power pads connect solid »). Un via fissuré reporte tout le courant sur l'autre paire et le blindage.
- **Correction :** Relier chaque pastille de masse à la patte de blindage voisine (0,32 mm plus loin) par une piste de 0,6 mm, élargir celle de droite, et passer les vias de masse en 0,8 / 0,4 mm.

#### X4A-01 · DATA ×4 · La broche 28 V du cordon, soudée à la main, est à 0,3 mm d'une ligne USB du hub et à 0,58 mm d'une pastille du hub

*Mineur · confirmé*

- **Où :** `J1` pastille 8 (`VIN`) à (89,0 ; 24,5), soudée à la main côté composants · piste `PORT4_DP` · `RN3` pastille 1 (`HUB_CFG2`)
- **Constat :** Mesuré sur le PCB, du bord de la pastille au cuivre voisin : piste `PORT4_DP` à 0,30 mm (sous vernis ; elle longe les huit pastilles de J1 sur 14 mm), piste `HUB_CFG2` à 0,34 mm, pastille 1 de `RN3` à 0,58 mm (joint brasé, vernis ouvert). Le connecteur lui-même est sûr, mais sur la carte la broche 20–28 V se trouve au milieu du domaine 3,3 V. La carte a déjà cette règle pour le connecteur SWD (zone interdite `swd-hdr`), pas pour J1. Sur la DATA ×6, seule une piste SCL sous vernis passe à 0,24 mm.
- **Conséquence :** Un pont de soudure vers `RN3`, ou un vernis entamé au-dessus de `PORT4_DP`, met VIN sur une broche du hub et, par le port 4, sur la ligne D+ d'une carte sous test. La limite de 1,76 A du nœud ne protège pas une broche 3,3 V. Les tests de JLC ne le verront pas : J1 est soudé après.
- **Correction :** Peu coûteux avant commande : une zone interdite autour des pastilles de J1 (1,5 mm autour de la 8), déplacer `RN3` de ≈ 2 mm, décaler la paire du port 4 d'au moins 1 mm vers l'ouest. Sur des cartes déjà faites : souder la broche 8 en dernier, Kapton sur `RN3`, contrôler à la loupe et à l'ohmmètre avant la première mise sous tension.

#### SYS-1 · Ensemble · Limites de courant non coordonnées : nœud 1,76 A, rangée 1,6 A, pleine échelle de mesure 1,64 A

*Mineur · confirmé*

- **Où :** Nœud : `R16` = 6,8 kΩ sur ILIM de `U9`, shunt `R19` = 50 mΩ · Hub : `R21–R24` = 7,5 kΩ sur ILIM des eFuses de rangée
- **Constat :** Fiche TPS2660 : I = 12 / R (kΩ), ± 5 %. Le nœud limite le cordon DATA à 1,68–1,85 A, alors que le hub limite toute la rangée, partagée par quatre baies, à 1,52–1,68 A. La protection aval est réglée plus haut que la protection amont. Par ailleurs l'INA226 sature à 81,92 mV / 50 mΩ = 1,638 A : toute la plage de limitation se lit en butée.
- **Conséquence :** Un cordon DATA en court-circuit ou en surcharge rencontre toujours la limite du hub avant la sienne : la rangée s'effondre jusqu'à ce que le nœud coupe, et les trois autres baies redémarrent. Le nœud ne peut pas non plus mesurer le courant auquel il limite. Le déroulé exact d'un court-circuit reste à mesurer sur table.
- **Correction :** `R16` = 8,2 kΩ (1,39–1,54 A) : au-dessus des 1,0–1,2 A annoncés pour une DATA ×6 chargée à 20 V, sous la pleine échelle de l'INA226, et le plus souvent sous la limite du hub. Pour une sélectivité complète, 9,1 kΩ (1,25–1,38 A) avec un plafond dans le micrologiciel. Changement de valeur seulement ; l'arbitrage revient au propriétaire.

#### X4A-02 · DATA ×4 · À la charge maximale déclarée, l'abaisseur 5 V dissipe 1,45 à 1,75 W dans un SOT-23-6, à 5 mm du berceau en PETG

*Mineur · à vérifier*

- **Où :** `U13` (LMR51635YDDCR) à (11,0 ; 4,6), `L2`, `C61–C67` · `design.py:911–915` (« 3.09 A … with no help from the node's firmware »)
- **Constat :** Le dimensionnement électrique est juste. Ce qui manque est un bilan thermique, et aucun document du dépôt ne relit ce convertisseur : l'audit des fiches lui est antérieur. D'après la courbe de rendement de TI (≈ 90 % à 24 V et 3 A), U13 dissipe ≈ 1,45 W à 20 V et ≈ 1,75 W à 28 V pour 3,09 A en sortie. La broche VIN arrive par une piste de 0,6 mm et la masse a deux vias, là où TI demande du cuivre large sur toutes les broches. Avec 55 à 70 °C/W : jonction vers 115–150 °C à 20 V et 130–165 °C à 28 V dans le tiroir fermé (150 °C admis, coupure à 165 °C). À 2,45 A : 95–120 °C.
- **Conséquence :** Rien aux charges habituelles (≤ ≈ 2 A au total). À pleine charge continue, le convertisseur peut atteindre sa coupure thermique, et la carte monte à 80–110 °C à côté d'une fente de berceau en PETG, qui ramollit vers 70–80 °C.
- **Correction :** Du cuivre et des vias sur VIN et sur la masse de U13 ; un plafond de ≈ 2,5 A dans le micrologiciel tant que ce n'est pas mesuré ; un essai au thermocouple, tiroir fermé, à 4 × 0,5 A pendant 30 minutes, à 20 V puis 28 V.

#### BN-02 · Nœud · Les entrées de l'INA226 sont reliées directement à la sortie 20–28 V du cordon, sans résistance de protection

*Mineur · probable*

- **Où :** `U10.10` ← `SHUNT_P`, `U10.9` et `U10.8` ← `SHUNT_N` · `C21` (1 µF) seul sur `DATA_VIN` · `D8` à J7
- **Constat :** TI recommande 10 Ω en série sur chaque entrée quand il n'y a pas de gros condensateur d'un côté du shunt, parce qu'un court-circuit franc donne un front qui déclenche les protections internes. Ici le côté charge n'a que 1 µF et finit sur 50 cm de cordon dans une chaîne porte-câbles. Sur un court-circuit, `DATA_VIN` passe de 28 V à ≈ −0,8 V en une microseconde environ ; l'INA226 est limité à −0,3 V et 5 mA par broche, sans rien pour borner ce courant.
- **Conséquence :** Un cordon DATA court-circuité sous tension peut détruire U10. La baie est alors hors service : le micrologiciel exige une réponse à 0x40 avant d'alimenter le cordon.
- **Correction :** Deux résistances de 10 Ω (0603) aux entrées de U10 et 100 nF entre les broches 10 et 9. C'est aussi le filtre que l'audit du dépôt garde en réserve pour la mise en route.

#### X6-04 · DATA ×6 · Brancher ou débrancher le cordon DATA sous tension peut renvoyer le 20–28 V par les lignes de signal

*Mineur · probable*

- **Où :** `J1` (B8B-PH, tous les contacts de même longueur) · ≈ 50 µF sur `VIN` (`C60` et quatre 10 µF) · `U4` · broches amont du hub. Même cordon et même connecteur sur la DATA ×4
- **Constat :** Le connecteur PH n'a pas de contact de masse en avance. Si VIN et une broche de signal touchent avant les deux masses, les condensateurs d'entrée se chargent à travers les lignes de signal : ≈ 1,1 mC à 20 V, jusqu'à la limite de l'eFuse pendant ≈ 0,7 ms, vers les broches I²C de l'ESP32 du nœud, son INA226 ou sa protection USB. L'ordre des broches aide : VIN est en bout, à côté d'une masse, donc une fiche qui entre de biais reste sûre. Le risque est une insertion à plat avec rebond. La surtension elle-même n'est pas un problème : la boucle est amortie et tout ce qui est sur VIN tient 50 V.
- **Conséquence :** Un branchement à chaud malchanceux peut détruire les broches I²C du nœud, son INA226 ou le port amont du hub. Or une carte de tiroir se change souvent.
- **Correction :** Micrologiciel d'abord : couper `DATA_VIN` dès que 0x20 ne répond plus, et ne le remettre que sur commande. Écrire « ne jamais brancher sous tension » dans la notice. Prochaine révision : 100–220 Ω en série sur SDA et SCL entre J1 et U4, et de même côté nœud.

#### BN-07 · Nœud · Le mode classique « même sans micrologiciel » ne donne plus accès à la carte sous test

*Mineur · confirmé*

- **Où :** `README.md:33`, `docs/architecture.md:95` · `R17` (10 kΩ, SHDN de U9 à la masse) · U5, U6, U7 alimentés en +3V3
- **Constat :** La logique des multiplexeurs est juste et ne dépend pas du micrologiciel. Mais le cordon DATA est coupé par défaut, et seul le micrologiciel l'alimente : sans lui, la carte DATA du tiroir (son hub, ses ports, son 5 V) reste éteinte et l'ordinateur ne voit rien. L'ancien interrupteur 5 V était passant par défaut ; cela a changé avec l'eFuse. Nœud non alimenté, les multiplexeurs sont ouverts aussi.
- **Conséquence :** Une promesse mise en avant dans le README n'est plus tenue : un nœud vierge ou en panne de micrologiciel ne laisse pas déboguer la carte sous test « à l'ancienne ».
- **Correction :** Corriger les deux textes. Garder la sortie 28 V coupée par défaut est le choix le plus sûr ; si le mode classique sans micrologiciel compte vraiment, il faut une décision de conception, pas une retouche.

#### SYS-7 · Ensemble · Si la commande part chez NextPCB : un autre fichier de placement, et des pistes plus fines que le palier retenu sur les deux cartes DATA

*Mineur · confirmé*

- **Où :** `fab/*-cpl-jlcpcb.csv` (les seuls fichiers de placement du dépôt) · DATA ×6 et DATA ×4 : pistes de 0,09–0,095 mm, isolement 0,1 mm · commentaires « NextPCB's 5/5 mil tier » dans `design.py` du nœud et du hub
- **Constat :**
  - **Placement :** les fichiers du dépôt portent les corrections de la bibliothèque JLC (rotations de 180° ou 270°, décalages d'origine). Un assembleur qui lit les rotations de KiCad doit recevoir le fichier de positions brut. Celui de la DATA ×6 a été contrôlé : ses 158 lignes sont celles du PCB.
  - **Ce qui tombe alors :** X6-01, BN-06, PH-01 (corrections JLC), PH-10 (empreinte JLC de l'inductance), et sans doute SYS-6 (stock JLC), selon la source d'approvisionnement de l'assembleur.
  - **Ce qui reste, quel que soit l'assembleur :** tous les constats de circuit et de routage, et les contrôles de sens dans l'aperçu de placement (point de U2, « + » de C60, embases USB-C, point de l'inductance du RP2350B).
  - **Finesse de gravure :** le nœud et le hub restent à 5 mil (aucune piste sous 0,127 mm, isolement 0,127 mm). Les deux cartes DATA descendent à 0,09 mm de piste (3,54 mil) et 0,1 mm d'isolement (3,94 mil). Avec la capacité de 3,5 / 3,5 mil (0,089 mm) que le propriétaire indique pour NextPCB, elles passent, mais sans marge sur la largeur : 1 µm sur les tronçons à 0,09 mm (0,3 mm de long sur la DATA ×6, 1,2 mm sur la DATA ×4), 6 µm sur ceux à 0,095 mm (116 et 263 mm).
- **Conséquence :** Les fichiers JLC envoyés tels quels à un autre assembleur tourneraient 18 pièces sur le hub, 21 sur le nœud, 29 sur la DATA ×6, 59 sur la DATA ×4 et 2 sur la carte caméra, et en décaleraient d'autres (13 sur le hub, 5 sur le nœud, 4 sur la carte caméra). Côté gravure, les deux cartes DATA sont au plancher du fabricant : fabricables, avec un rendement moins confortable qu'à 5 mil.
- **Correction :** Exporter le fichier de positions KiCad brut pour chaque carte et le dire dans la commande. Vérifier que le devis des deux cartes DATA est bien fait au palier 3,5 / 3,5 mil, et faire confirmer la lumière des embases USB-C (X6-09), dont le minimum cité vient de JLC. Au prochain routage, repasser à 0,127 mm les pistes fines là où il y a la place.

#### BN-04 · Nœud · Brancher un nœud sur une rangée sous tension fait chuter toute la rangée

*Mineur · à vérifier*

- **Où :** `Q1`, `R1`, `D1`, `C1` (100 µF) · UVLO de `U9` · `docs/power.md`, « Protection chain »
- **Constat :** Une fois passant, Q1 conduit dans les deux sens : les condensateurs des nœuds déjà en service se déchargent dans celui du nouveau venu, et le hub ne fournit que 1,6 A. Par partage de charge, une rangée à 20 V tombe à ≈ 10 V avec un nœud déjà présent, 13,3 V avec deux, 15 V avec trois. Les eFuses DATA des voisins coupent entre 13,25 et 14,75 V, les abaisseurs entre 9,8 et 11,9 V. Calculé, non mesuré ; la doc ne parle que de la surtension au branchement.
- **Conséquence :** À 20 V, ajouter un nœud à une rangée d'un ou deux nœuds coupe l'alimentation de leurs cartes sous test, et redémarre probablement le nœud s'il est seul.
- **Correction :** Écrire dans la notice « couper la rangée au hub avant de brancher ou débrancher un câble de rangée », et le confirmer sur table avec deux nœuds à 20 V.

#### BN-05 · Nœud · La ligne de données de la LED d'état longe D+ de la paire USB haute vitesse

*Mineur · confirmé*

- **Où :** `LED_DIN` (`U3.31` → `R8`, routage automatique) contre `PC_DP` (tracé à la main), F.Cu, x ≈ 30,5, y 37–66
- **Constat :** Mesuré sur le PCB : ≈ 25 mm de `LED_DIN` à moins de 0,3 mm bord à bord de `PC_DP`, dont 7 mm à 0,18 mm. L'écart de la paire elle-même est de 0,15 mm, et D− est 0,4 mm plus loin : le couplage est différentiel. La règle du dépôt tient les réseaux « sensibles » à trois largeurs de piste d'une paire USB, mais `LED_DIN` n'est dans aucune classe.
- **Conséquence :** Estimation : 20 à 60 mV sur D+ à chaque front, pour une excursion de 400 mV, sur un canal qui a déjà deux multiplexeurs, deux protections, deux connecteurs et 50 cm de cordon. Des réémissions au pire, en mode classique, quand la LED est rafraîchie.
- **Correction :** Tenir `LED_DIN` à 0,75 mm au moins de la paire (couloir interdit le long du tracé, ou passage sur B.Cu), ou la mettre dans une classe soumise à la règle d'écart USB.

#### SYS-2 · Ensemble · La documentation décrit encore l'ancienne alimentation en 5 V, sur le nœud comme sur la DATA ×4

*Mineur · confirmé*

- **Où :** `docs/electronics.md` (sections nœud et DATA ×4) · `docs/datasheet-audit.md:183–196` · `docs/architecture.md:8–9` · `docs/power.md:90` · `firmware/README.md`
- **Constat :**
  - **DATA ×4 :** J1 est décrit avec INT en broche 1 et +5V en broche 8. Le PCB reçoit le 20–28 V en broche 8, laisse la broche 1 libre et fabrique son 5 V sur la carte.
  - **DATA ×6 :** carte par défaut de chaque tiroir, sans section dans `electronics.md`.
  - **Nœud :** l'audit des fiches techniques traite U9 comme un TPS2553 sur 5 V (« passant sans micrologiciel », 22 µF, mode commun 5,24 V). Le TPS26600 du nœud, avec ses valeurs propres et l'INA226 à 28 V, n'a jamais été audité comme tel.
  - Détails : fusible réarmable caméra donné à 0,5 A (il fait 0,75 A), « GND sur les broches 2 et 4 » de J6 (ce sont SCK et MOSI), diviseur PC_DET « 10k/20k » (18 kΩ), tirage POS_IN « 100k » (150 kΩ).
  - **Hub :** la notice décrit une LED PD qui « respire » ou clignote ; elle est simplement allumée tant que le contrat est en place. La finition est donnée ENIG alors que la carte est en HASL sans plomb.
  - **28 V EPR :** `docs/power.md` garde le 28 V verrouillé parce que l'inductance de la DATA ×4 serait encore une FXL0630 de 30 V. Sur le PCB, c'est une IHLP2525CZ de 75 V, comme sur les autres cartes : la raison donnée n'existe plus.
  - **Comptes :** 91 ou 92 pièces non montées sur la base selon la doc ; il y en a 99. Longueurs des paires USB, position de J1 et des encoches, liste des points de test : périmés aussi.
- **Conséquence :** Quelqu'un qui met une carte sous tension sur table en suivant la doc alimentera en 5 V une entrée prévue pour 20–28 V, ou l'inverse. Et le constat BN-01 est passé à travers l'audit parce que celui-ci raisonnait sur l'ancien circuit.
- **Correction :** Réécrire les sections DATA ×4 et nœud à partir de `design.py`, ajouter une section DATA ×6, refaire l'audit de U9 comme TPS26600, mettre à jour le tableau des mesures de mise en route.

#### BN-06 · Nœud · La diode D8 sera posée 0,34 mm à côté de ses pastilles

*Mineur · confirmé*

- **Où :** `D8` (DFLS260-7, C209346, PowerDI-123) · `fab/bay-node-cpl-jlcpcb.csv` · pas d'entrée dans `JLC_CPL_FIX`
- **Constat :** L'empreinte KiCad a son origine au centre du boîtier (pastilles à −0,85 et +1,525 mm). Celle de JLC a son origine à mi-chemin des pastilles (±1,187 mm). Même orientation, mais 0,34 mm d'écart le long de la diode. D8 a été ajoutée après l'audit de placement du dépôt, dont le seuil était 0,10 mm. Ce constat ne vaut que pour le fichier corrigé pour JLC ; un fichier de positions KiCad brut donne le centre du boîtier.
- **Conséquence :** La refusion recentrera probablement la pièce, sans garantie. Les diodes D41–D44 du hub ont le même décalage (PH-01).
- **Correction :** Ajouter `"C209346": ("D_PowerDI-123", 0, 0.3375, 0.0)` à `JLC_CPL_FIX` et contrôler dans l'aperçu JLC.

#### X4B-01 · DATA ×4 · À la coupure, les LSF0108 restent passants 10 à 20 ms et laissent une carte sous test encore alimentée pousser du courant dans les CH446Q éteints

*Mineur · probable*

- **Où :** `PORTn_VREFB` : `R111–R411` (200 kΩ vers +5V_MX), `C105–C405` (100 nF), `U107–U407` broches 19 et 20 · `design.py:630–632`
- **Constat :** EN et Vref_B ne se déchargent que par la résistance de 200 kΩ : τ = 200 kΩ × 100 nF = 20 ms, alors que +5V_MX tombe en quelques millisecondes. Pendant ≈ 19 ms (VREF 3,3 V) ou ≈ 10 ms (1,8 V), chaque broche haute d'une carte encore vivante envoie ≈ 20 mA à travers 100 Ω dans une broche X dont le VDD est à 0 V. TI demande EN bas à la mise hors tension (SDLS966M §8.3.2), et WCH limite les broches analogiques à VDD + 0,5 V.
- **Conséquence :** Dépassement répété des valeurs limites des CH446Q, limité en courant par les 100 Ω. Pas de dégât attendu, mais rien dans la fiche WCH ne le couvre, et l'isolement annoncé « carte éteinte » n'est pas tenu pendant ces millisecondes.
- **Correction :** Une diode 1N4148WS par port de `PORTn_VREFB` (anode) vers `+5V_MX` (cathode), pour que EN suive le rail à la coupure. Sans pièce nouvelle : passer `C105–C405` à 10 nF, ce qui réduit la fenêtre d'un facteur dix sans la fermer.

#### PH-01 · Hub · Les quatre diodes de sortie de rangée seront posées 0,34 mm à côté de leurs pastilles

*Mineur · confirmé*

- **Où :** `D41–D44` (DFLS260-7, C209346) · `fab/power-hub-cpl-jlcpcb.csv` · pas d'entrée dans `JLC_CPL_FIX`
- **Constat :** Même cause que BN-06 sur le nœud : l'origine de l'empreinte KiCad est au centre du boîtier, celle de JLC à mi-chemin des pastilles, 0,34 mm plus loin. La pièce est arrivée après l'audit de placement du dépôt. Ce constat ne vaut que pour le fichier corrigé pour JLC ; un fichier de positions KiCad brut donne le centre du boîtier.
- **Conséquence :** La patte d'anode, large de 1,05 mm, se retrouve décalée d'un tiers. La refusion peut la recentrer, ou laisser un joint faible sur une diode dont le rôle est d'encaisser la coupure d'un court-circuit.
- **Correction :** La même ligne règle les deux cartes : `"C209346": ("D_PowerDI-123", 0, 0.3375, 0.0)` dans `JLC_CPL_FIX`.

#### X4B-02 · DATA ×4 · Au repos, un bus de la matrice se tient entre 2,1 et 2,8 V au lieu de 3,3 V tant que le RP2350B garde ses tirages de reset

*Mineur · probable*

- **Où :** `RN8`, `RN9` (10 kΩ vers +3V3) · `RN6`, `RN7` (2,2 kΩ vers GPIO10–13 et 16–19) · `U11` GPIO2–9
- **Constat :** Toutes les broches du RP2350B démarrent avec un tirage à la masse de 36 à 113 kΩ. Chaque bus en voit deux : sa broche d'analyseur, et sa broche de commande du 2,2 kΩ. Pire cas : 36 k ∥ 38,2 k = 18,5 kΩ contre 10 kΩ, soit 2,11 V ; typique 2,57 V. L'audit du dépôt n'en comptait qu'un (2,58 V au pire). Cet état dure de chaque mise sous tension jusqu'à ce qu'une image retire les tirages ; le RP2350B n'a pas de flash.
- **Conséquence :** Un fil virtuel dont le seul tirage est celui de la carte arrive à 2,1–2,8 V sur une carte sous test en 3,3 V, sous le seuil haut CMOS de 2,31 V dans la moitié basse de la plage. Les signaux push-pull et l'I²C avec tirages côté carte sous test ne sont pas touchés.
- **Correction :** D'abord dans le micrologiciel : retirer les tirages de GPIO2–13 et 16–19 avant toute autre chose, et vérifier ce que fait l'image d'analyseur d'origine. Sinon passer `RN8`/`RN9` à 4,7 kΩ (repos ≥ 2,61 V au pire).

#### X4B-03 · DATA ×4 · Un seul via relie la masse du RP2350B au plan

*Mineur · confirmé*

- **Où :** `U11` pastille 81 (3,4 × 3,4 mm) · seul via GND sous la pastille : (47,565 ; 13,465), 0,5 / 0,3 mm · `design.py:1708–1710`
- **Constat :** La pastille centrale est la seule masse de la puce en dehors de VREG_PGND, et le retour de tous ses condensateurs de découplage passe par ce via. Électriquement il suffit (≈ 0,1 nH vers In1), mais il n'y a aucune redondance. Les autres QFN de la carte en ont quatre à neuf.
- **Conséquence :** Un via ouvert sous une pastille soudée, qui aspire la brasure, devient un point de défaillance unique pour tout le coprocesseur.
- **Correction :** Ajouter des vias aux autres croisements des fenêtres de pâte : (46,435 ; 12,335) est libre aujourd'hui ; deux autres se libèrent en décalant BUS_A et BUS_B de 0,2–0,3 mm sur B.Cu. Viser quatre.

#### X6-07 · DATA ×6 · Le 5 V est réglé à 5,24 V et peut atteindre 5,39 V à vide

*Mineur · confirmé*

- **Où :** `R52`/`R53`, `R54`/`R55` (100 kΩ / 18 kΩ, 1 %) · `design.py:417–418`
- **Constat :** 0,8 V × (1 + 100/18) = 5,244 V ; 5,11 à 5,39 V avec les tolérances. USB 2.0 admet 4,75–5,25 V sur un port aval. La DATA ×4 est passée à 18,7 kΩ (5,08 V) pour cette raison ; la DATA ×6 est restée à 18 kΩ.
- **Conséquence :** Dans les limites de l'USB Type-C (5,5 V), hors de celles d'USB 2.0 en haut de tolérance. Rien n'est abîmé, mais un banc de mesure ne devrait pas être l'exception sur VBUS. Cette tension alourdit aussi la dissipation du régulateur 3,3 V (X6-02).
- **Correction :** `R53` et `R55` à 18,7 kΩ : 5,08 V (4,94–5,22 V), et VBUS reste ≥ 4,78 V à 0,5 A.

#### X4B-05 · DATA ×4 · Le sens de pose de l'inductance du régulateur de cœur n'est confirmé par personne

*Mineur · à vérifier · connu*

- **Où :** `L1` (Abracon AOTA-B201610S3R3, C42411119), pastille 1 sur `+1V1` · ligne CPL `L1, 180°`, sans entrée dans `JLC_CPL_FIX`
- **Constat :** Le dessin est juste : la pastille repérée est sur la sortie, comme sur la figure 26 de Raspberry Pi. Ce qui reste ouvert est la position du point sur la pièce en bande par rapport à la pastille 1 de l'empreinte JLC : l'audit du dépôt note que le symbole et la sérigraphie JLC ne s'accordent pas, et Abracon marque « + » l'extrémité que Raspberry Pi marque « − ».
- **Conséquence :** Raspberry Pi indique que le régulateur demande le bon sens, surtout à fort courant. Si la pièce est posée à l'envers, le défaut serait majeur pour la variante logique.
- **Correction :** Dans l'aperçu de placement JLC puis sur la première carte, le point blanc doit être sur la pastille est, du côté de `C33`. Sinon, ajouter 180° pour C42411119 dans `JLC_CPL_FIX`. Mesurer ensuite 1,1 V ± 3 % en charge.

#### X6-05 · DATA ×6 · L'abaisseur B est dimensionné à 96 % de son courant nominal, avec ≈ 1,0 à 1,3 W dans un SOT-23-6

*Mineur · probable*

- **Où :** `U14`, `L3` (`+5V_B` : ports 4–6 à leur limite, 3 × 0,644 A, plus le régulateur 3,3 V, 0,46 A = 2,39 A) · deux vias de masse près de la broche 4
- **Constat :** Courant crête à 28 V : 2,80 A nominal, 2,96 A avec l'inductance à −20 % et la fréquence au minimum, pour une limite crête minimale de 2,9 A. Rendement lu sur la figure 6-8 de TI : ≈ 91 % à 20 V, ≈ 89 % à 28 V, soit 1,0 à 1,3 W dans U14. TI demande du cuivre large sur chaque broche et une rangée de vias de masse ; ici VIN arrive par une piste de 0,6 mm et la masse a deux vias.
- **Conséquence :** Rien avec de vraies cartes sous test (quelques centaines de mA). Au maximum documenté, sur un rack en 28 V, l'abaisseur B peut limiter ou cycler thermiquement, ce qui fait tomber le hub, alimenté par le même rail.
- **Correction :** Au choix : annoncer 0,5 A par port en continu et le faire tenir par le micrologiciel ; ajouter des vias de masse et élargir le cuivre ; ou monter le LMR51635 (3,5 A, même brochage) en U14.

#### X6-06 · DATA ×6 · La commande de marche des abaisseurs parcourt 83 mm en haute impédance le long d'un nœud de commutation

*Mineur · probable*

- **Où :** `BUCK_EN` : `R50`/`R51` près de l'abaisseur B → `U14.2` et, à travers tout le haut de la carte, → `U13.2` · piste de 0,095–0,127 mm, sans condensateur
- **Constat :** En arrivant sur U13, la piste longe le cuivre de `BUCKA_SW` sur 5,3 mm (0,25 mm au plus près), frôle la pastille du condensateur d'amorçage, puis passe sous le boîtier. Ce nœud bascule de 20–28 V en quelques nanosecondes, 1,1 million de fois par seconde, et la source de EN fait 9,1 kΩ. Estimation : des pointes de 0,15 à 0,3 V. À 20 V il reste 0,74 V de marge ; elle fond quand VIN s'approche du seuil d'arrêt.
- **Conséquence :** Arrêts et redémarrages intempestifs possibles de l'abaisseur A seul, surtout à VIN bas : une panne intermittente difficile à trouver.
- **Correction :** 1 à 10 nF de EN à la masse près de U13 (et de U14). Ou donner à l'abaisseur A son propre diviseur local et supprimer la longue piste.

#### CP-1 · Caméra · Les noms sérigraphiés du connecteur caméra ne tombent pas en face des broches

*Mineur · confirmé*

- **Où :** `J2`, texte « VCC GND SCK MISO MOSI CS » centré sous le connecteur (`design.py:171`)
- **Constat :** Le texte est une seule chaîne de 17,4 mm de large pour six broches qui en occupent 12,7. « MOSI » est centré à x ≈ 18,1 mm, exactement entre la broche 5 (16,81) et la broche 6 (19,35) ; « CS » est 1,6 mm au-delà de la broche 6 et « VCC » 1,2 mm avant la broche 1.
- **Conséquence :** Avec un câble de Mega terminé par des fils Dupont séparés, MISO, MOSI et CS peuvent être décalés d'une broche. L'ordre reste juste, et un connecteur 6 points monobloc ne pose pas de problème.
- **Correction :** Un libellé par broche au pas de 2,54 mm (texte de 0,6 mm, ou libellés tournés à 90°).

#### X6-11 · DATA ×6 · Quatre pièces polarisées ou orientées sans référence JLC : à contrôler dans l'aperçu de placement

*Mineur · à vérifier*

- **Où :** `C60` (33 µF 50 V, C240518) · `J101–J601` (USB-C, C5181332) · `Y1` (C15643) · avec `U2` (X6-01) · mêmes pièces sur la DATA ×4 (`C60`, `J101–J401`)
- **Constat :**
  - **C60**, sur le 20–28 V : l'empreinte JLC a sa pastille 1 du même côté que KiCad, mais son symbole ne dit pas laquelle est le « + ». Un électrolytique à l'envers sur 28 V évente.
  - **Embases USB-C** : JLC n'a pas d'empreinte pour cette référence, donc rien contre quoi vérifier la rotation.
  - **Quartz** : tourné de 180° il fonctionne, de 90° non.

  Les LED de port (C2297) ont été vérifiées : correctes sans correction.
- **Correction :** Cocher ces pièces dans l'aperçu JLC, et inscrire C240518 dans `JLC_CPL_FIX` avec sa valeur vérifiée, même si elle est nulle.

#### X6-09 · DATA ×6 · Les trous de centrage des embases USB-C suivent un plan GCT périmé, et la lumière est plus étroite que le minimum de JLC

*Mineur · probable*

- **Où :** Empreinte `bench:USB_C_Receptacle_GCT_USB4145-03-0170-C_Vertical` (`footprints.py:206–247`) · `J101–J601`. Même empreinte sur la DATA ×4
- **Constat :** L'empreinte reprend le plan rév. A1 : trou Ø 0,66 et lumière 0,86 × 0,66. Le plan actuel (rév. A2, janvier 2023) demande Ø 0,71 et 1,01 × 0,71, pour des ergots de Ø 0,56 ± 0,05. Avec la tolérance de perçage de JLC (± 0,05), un trou de 0,66 peut sortir à 0,61 face à un ergot de 0,61. Le reste de l'empreinte concorde avec la rév. A2. Par ailleurs la lumière non métallisée de 0,66 mm de large est sous le minimum de 1,0 mm que JLC annonce pour une lumière non métallisée (chiffre relevé sur le site de JLC, non confirmé auprès d'eux).
- **Conséquence :** Certaines embases peuvent ne pas descendre à plat à la pose, six par carte. Une embase verticale de travers gêne aussi le peigne du berceau, ajusté à 0,1 mm. JLC peut aussi poser une question d'ingénierie, ou remplacer la lumière par un trou rond sans prévenir.
- **Correction :** Ø 0,71 pour le trou rond ; pour le second, un trou rond non métallisé Ø 0,90 ou la lumière 1,01 × 0,71 de la rév. A2, à valider avec JLC avant commande. Vérifier ensuite le dégagement du cuivre voisin. L'empreinte est commune aux DATA ×4 et ×6.

#### X4A-03 · DATA ×4 · Une coupure brève de l'alimentation peut ne pas réinitialiser les expandeurs

*Mineur · probable*

- **Où :** `U2`, `U6` (TCA6408A), ~RESET tiré à +3V3 par `R11`, `R12` seulement · rails sans résistance de décharge · `U5`. Vaut aussi pour `U10` (TCA9534A, sans broche de reset)
- **Constat :** Le TCA6408A ne réarme sa remise à zéro que sous 0,7 V. Sous ≈ 1,5 V il ne reste que des fuites pour décharger ≈ 120 µF : 2 à 10 secondes estimées pour descendre à 0,65 V. C'est le même mécanisme que X6-08 sur la DATA ×6.
- **Conséquence :** Après un cycle d'alimentation plus court, les ports qui étaient allumés se rallument seuls, ou les lignes EN, RESET et BOOT sont dans un état quelconque jusqu'à la réécriture par le nœud : une carte sous test peut voir une impulsion de reset ou un bref VBUS.
- **Correction :** Relier `EXP1_RST_N` et `EXP2_RST_N` à `HUB_RST_N` (le superviseur U5 existe déjà ; R11 et R12 disparaissent) et ajouter 1 kΩ du +3V3 à la masse, qui couvre aussi U10. Dans le micrologiciel : écrire le registre de sortie avant celui de configuration.

#### X6-08 · DATA ×6 · Une coupure brève de l'alimentation peut ne pas réinitialiser le TCA9535

*Mineur · à vérifier*

- **Où :** `U2` (sans broche de reset) · rails `+3V3`, `+5V_A`, `+5V_B`, sans résistance de décharge
- **Constat :** Le TCA9535 ne remet ses registres à zéro que si son alimentation descend sous 0,75 V. Rien ne décharge les rails : une fois le hub arrêté vers 1,5–2 V, il ne reste que des fuites et les diviseurs de 118 kΩ, soit plusieurs secondes de constante de temps.
- **Conséquence :** Après une coupure courte, les ports qui étaient allumés se rallument à la remontée du 3,3 V, avant toute écriture du nœud, et une machine I²C bloquée n'est pas débloquée. Le hub, lui, a son superviseur.
- **Correction :** Micrologiciel : tenir `DATA_VIN` coupé pendant une durée mesurée à l'oscilloscope, et toujours réécrire les registres de sortie puis de configuration au démarrage. Prochaine révision : 1 kΩ du +3V3 à la masse, ou un TCA9539 (avec reset) piloté par le superviseur.

#### PH-03 · Hub · Une piste de signal passe sous l'entretoise métallique d'un trou de fixation

*Mineur · confirmé*

- **Où :** `H3` à (4 ; 93,5) · piste `ON_A` (F.Cu, 0,25 mm), bord à 2,29 mm du centre du trou · `H1–H4` sans pastille
- **Constat :** Le hub est tenu par des entretoises hexagonales M3 en laiton, serrées en tournant sur la face composants. Une entretoise de 5,5 mm couvre un rayon de 2,75 à 3,18 mm : la piste `ON_A` est dessous, protégée par le seul vernis, avec la zone de masse à côté. Les trois autres trous n'ont aucune autre piste à moins de 3,5 mm.
- **Conséquence :** Une entretoise qui raye le vernis en tournant relie `ON_A` à la masse : la LED « ON » de la rangée A reste éteinte alors que la rangée est alimentée. Rien n'est abîmé (18 kΩ en série), mais on croirait la rangée morte.
- **Correction :** Écarter `ON_A` à 3,6 mm ou plus du centre de H3, ou ajouter une zone interdite de Ø 7,5 mm autour de chaque trou. Mieux : des trous à pastille reliés à la masse.

#### X4A-06 · DATA ×4 · Le point de test du 28 V est à 1,45 mm de celui de SDA

*Mineur · confirmé*

- **Où :** `TP40` (VIN, Ø 1,5) à (91,0 ; 50,5) et `TP24` (SDA, Ø 1,0) à (91,0 ; 53,2), nus, en face arrière · `design.py:182–184`
- **Constat :** Une pointe de sonde qui touche les deux met 20–28 V sur SDA : quatre INA226 (6 V maximum), les expandeurs, et par la diode de corps de Q1 le cordon, l'INA226 du nœud et une broche de son ESP32.
- **Correction :** Échanger TP24 avec le point de masse TP26, ou éloigner TP40 d'au moins 5 mm de tout point de signal.

#### PH-04 · Hub · Brancher la console USB à chaud peut amener le régulateur 3,3 V à sa tension maximale absolue

*Mineur · à vérifier*

- **Où :** `J6` → `USB_VBUS` → `C120` (1 µF), `U5`, `D5` → `+5V` → `C111` (1 µF), `U3` (AP2112K)
- **Constat :** Depuis un port USB-A, le 5 V est présent avant l'insertion : le câble résonne avec les ≈ 2 µF de céramique de la carte, soit 6,2 à 7,9 V sans écrêtage et ≈ 6,3–6,8 V après l'USBLC6. La diode D5 transmet ce pic au +5V, qui n'a que 1,1 µF : ≈ 6,0–6,5 V pendant quelques dizaines de microsecondes, pour 6,5 V maximum absolu sur l'AP2112K. Estimation, non mesurée. Un câble USB-C vers USB-C ne fait pas cela.
- **Conséquence :** À la limite du régulateur à chaque branchement à chaud avec un câble A vers C court. Probablement supportable, mais sans marge.
- **Correction :** `C111` de 1 µF à 10 µF sur les mêmes pastilles 0805, et une mesure à l'oscilloscope à la mise en route.

#### X4A-07 · DATA ×4 · Le VBUS d'un port coupé reste vers 2,5 V pendant de longues secondes

*Mineur · probable · connu*

- **Où :** `D101–D401` et `R114–R414` sur `PORTn_5V_SW` · `C102–C402` · entrée VBUS des INA226
- **Constat :** Port coupé, la LED et sa résistance déchargent le condensateur de port, mais seulement jusqu'au seuil de la LED verte (≈ 2,5 V). Ensuite il ne reste que les 830 kΩ de l'INA226 : 10 à 18 s de constante de temps. Le TPS2553-1 n'a pas de décharge de sortie. La LED reçoit ≈ 2,2 mA, pas les ≈ 3 mA des notes.
- **Conséquence :** « Redémarrer la carte sous test » la laisse vers 2 V pendant des secondes : une carte sans détection de sous-tension peut mal repartir, et la règle « refuser EN tant que VBUS est présent » demande une longue attente.
- **Correction :** 2,2 kΩ de `PORTn_5V_SW` à la masse, avant le shunt pour ne pas fausser la mesure : VBUS sous 0,3 V en ≈ 100 ms.

#### CP-2 · Caméra · Peu de cuivre pour évacuer la chaleur du régulateur 3,3 V

*Mineur · probable · connu*

- **Où :** `U1` (AP2114H-3.3, SOT-223) · zones `ldo-tab` (F.Cu, 22,8 mm²) et `ldo-tab-b` (B.Cu, 29,1 mm²), trois vias
- **Constat :** La languette est à VOUT, donc seul le cuivre +3V3 la refroidit : environ 52 mm² en tout, alors que les deux faces sont surtout des plans de masse. Au courant maximal de la Mega (317 mA), le régulateur dissipe ≈ (5,0 − 3,3) V × 0,317 A ≈ 0,54 W. Avec les 128 °C/W que la doc du projet retient pour ce boîtier sans cuivre, l'échauffement est de l'ordre de 55 à 70 °C.
- **Conséquence :** Jonction vers 100–115 °C dans un boîtier fermé à 40–45 °C lors des captures en rafale, près de la limite de 125 °C. En flux vidéo typique (≈ 180 mA) la marge est large. La mesure est déjà prévue à la mise en route.
- **Correction :** Agrandir l'îlot +3V3 de la face arrière (la face arrière est presque entièrement en plan de masse, il y a de la place) et ajouter quelques vias près de la languette.

#### X4B-04 · DATA ×4 · La broche DVDD 10 du RP2350B est en bout de chaîne avec le découplage le plus faible

*Mineur · confirmé · connu*

- **Où :** `+1V1` : sortie → broche 51 → broche 32 (`C47` 4,7 µF) → broche 10, à 18,7 mm de la sortie · `C46` (100 nF) à 6,5 mm et deux vias de la broche 10
- **Constat :** Raspberry Pi demande 100 nF près des deux DVDD les plus proches du régulateur et 4,7 µF à la plus éloignée. Ici le 4,7 µF est au milieu de la chaîne, et le condensateur de la dernière broche est deux fois plus loin que sur leur carte de référence. L'exception est déjà déclarée dans `decoupling_order_exempt`.
- **Conséquence :** Marge réduite sur les transitoires du cœur. Fonctionnera très probablement, la charge de l'analyseur étant stable.
- **Correction :** Sans pièce nouvelle : `C46` en 4,7 µF (C23733, déjà dans la nomenclature).

#### X4B-06 · DATA ×4 · Un I²C en 1,8 V sur fil virtuel ne tient pas son niveau bas avec les 2,2 kΩ en service

*Mineur · probable · connu*

- **Où :** `U7`, `U8` (CH446Q à ±5 V) · `RN6`, `RN7` · chaînes 100 Ω + LSF0108
- **Constat :** WCH ne donne la résistance passante qu'à 12 V (45/65 Ω) et à 5 V (120/185 Ω) ; à ±5 V elle n'est pas spécifiée. En comptant les deux chaînes d'un fil réel et des tirages de 4,7 kΩ sur chaque carte sous test, un niveau bas en 1,8 V vaut 0,55–0,65 V avec le 2,2 kΩ, pour une limite de 0,54 V, même à 65 Ω. Avec le 10 kΩ seul : 0,25–0,30 V, correct.
- **Conséquence :** Erreurs I²C sur des cartes en 1,8 V si le micrologiciel active les 2,2 kΩ. En 3,3 V la marge existe tant que le −5 V est présent.
- **Correction :** Règle de micrologiciel et de documentation, sans retouche de carte : les 2,2 kΩ pour les fils en 3,3 V seulement ; refuser les fils quand GPIO45 signale l'absence du −5 V. Garder la mesure de la résistance passante à la mise en route.

#### BN-08 · Nœud · AUX prend la même fiche que la sortie de rangée, et ses lignes ne sont pas protégées

*Mineur · confirmé · connu*

- **Où :** `J5` (AUX) et `J2` (ROW OUT), deux S6B-PH à 22 mm l'un de l'autre sur le bord droit · `J7.6`, `J7.7` (I²C)
- **Constat :** Un cordon AUX branché dans le J2 libre du dernier nœud d'une rangée met VRACK (J2.6) sur un fil relié à la carte sous test. AUX_TX et AUX_RX n'ont que 1 kΩ vers l'ESP32, sans protection contre les décharges ; les drains de Q2 et Q3 vont droit aux broches. SDA et SCL de J7 arrivent à l'ESP32 et à U10 sans protection ni résistance. Déjà relevé par la revue de schéma du dépôt (S3, S5).
- **Correction :** À la prochaine révision : un autre nombre de broches pour AUX, un USBLC6 sur TX/RX. En attendant, activer le tirage interne de AUX_RX.

#### BN-09 · Nœud · Éclairage caméra en PWM : fronts rapides sur le cordon qui porte aussi le SPI

*Mineur · à vérifier*

- **Où :** `Q4` (AO3400A), grille `CAM_LED` reliée directement à `U3.7` (IO7) avec `R36` 100 kΩ à la masse · `LED_K` sur J6.6, entre MISO et CS · cordon de ≈ 50 cm
- **Constat :** La grille n'a pas de résistance série. En PWM à 20 kHz ou plus, les ≈ 100 mA des LED sont commutés en quelques dizaines de nanosecondes dans une boucle de 50 cm (CAM_5V en broche 3, LED_K en broche 6) qui entoure MOSI et MISO.
- **Conséquence :** De l'ordre de 0,4 à 0,8 V induits sur MISO pendant chaque front, 40 000 fois par seconde quand la caméra diffuse : des images corrompues de temps en temps si l'éclairage est gradué. Sans effet en tout ou rien.
- **Correction :** 470 Ω à 1 kΩ entre IO7 et la grille de Q4 (fronts de ≈ 1 µs, soit 2 % d'une période). Observer MISO à l'oscilloscope, éclairage en PWM, à la mise en route.

#### X6-10 · DATA ×6 · Les MOSFET d'isolation I²C sont des 2N7002, dont le seuil peut atteindre 2,5 V pour une grille à 3,3 V

*Mineur · probable · connu*

- **Où :** `Q1`, `Q2` (C8545), grilles sur `+3V3`. Même montage sur la DATA ×4
- **Constat :** Le montage est juste. Mais quand le nœud tire la ligne à la masse, le côté carte suit d'abord par la diode de corps, ce qui ne laisse que ≈ 2,6 V de tension de grille : un transistor au pire cas, à froid, conduit à peine. Niveau bas vu côté carte : 0,5 à 0,7 V pour un seuil de 0,99 V, sur 40–50 cm de cordon non blindé. Déjà noté comme mesure de mise en route.
- **Correction :** Mesurer le niveau bas côté carte dans les deux sens, à froid. S'il est juste : un BSS138 (seuil 0,8–1,5 V) sur la même empreinte.

#### PH-05 · Hub · Environ 140 µF directement sur VBUS, pour 10 µF attendus par l'USB PD à l'insertion

*Mineur · confirmé · connu*

- **Où :** `C8` (100 µF), quatre 10 µF, quatre 1 µF, tous sur VRACK = VBUS · `docs/power.md`, décision du 20 octobre 2026
- **Constat :** Choix assumé et documenté, avec un essai prévu sur trois chargeurs. Un point que la doc ne mentionne pas : rien ne décharge cette capacité. Après un débranchement, VRACK met 2 à 6 secondes à descendre à 0,8 V.
- **Conséquence :** Un chargeur à détection de court-circuit rapide peut refuser l'insertion. Un rebranchement dans les secondes qui suivent trouve 1 à 3 V sur VBUS ; une source qui exige 0 V d'abord attend.
- **Correction :** Garder l'essai prévu. Si un chargeur rechigne : une résistance de décharge de 4,7 kΩ sur VRACK (0,17 W à 28 V) ramène la décroissance sous la seconde.

#### PH-06 · Hub · L'option 28 V n'a aucune marge : les fenêtres du CH224A, de la TVS et des eFuses se chevauchent

*Mineur · confirmé · connu*

- **Où :** `U1` (CH224A) derrière `R5` 56 Ω et `C4` 1 µF · `D1` (SMAJ30A) · `U11–U14`
- **Constat :** Un contrat 28 V peut se tenir à 29,4 V. Le CH224A admet 30 V en service et 32 V au maximum absolu ; la TVS ne commence à conduire qu'à 33,3 V, donc elle ne protège jamais U1. Une eFuse déclenchée en surtension ne se réarme que sous 28,5 à 31,5 V : sous un contrat légal à 29 V, la rangée peut rester coupée. Tout le reste de VRACK tient l'écrêtage à 48,4 V.
- **Conséquence :** Aucune à 20 V, le chargeur par défaut : 11 V de marge. À 28 V, un chargeur défaillant ou mal régulé coûte U1, et une surtension peut laisser des rangées coupées.
- **Correction :** Rien à faire pour la version 20 V. Avant de déverrouiller le 28 V : garder le repli du micrologiciel vers 20 V, mesurer VHV sur le passage de 9 à 28 V et sur une coupure de rangée chargée.

### Remarques (24)

#### SYS-3 · Ensemble · Tout le câblage repose sur des cordons « same direction »

*Remarque · confirmé*

- **Où :** Câble de rangée PH 6, cordon DATA PH 8, cordon caméra PH 8
- **Constat :** Les trois câbles supposent un cordon tout fait où la broche n d'un bout arrive sur la broche N + 1 − n de l'autre. Les vendeurs n'emploient pas tous « same direction » et « reverse » dans le même sens. Les brochages ont été choisis pour qu'un cordon du mauvais type soit sans danger (le 20–28 V tombe sur une broche libre ou sur une masse), mais alors rien ne fonctionne.
- **Correction :** Vérifier chaque lot de cordons au testeur de continuité avant la première mise sous tension, et l'écrire dans la notice d'assemblage.

#### SYS-4 · Ensemble · Le retour de courant du cordon DATA passe par deux fils de masse sur trois

*Remarque · confirmé*

- **Où :** Nœud `J7.8` (GND) ↔ DATA ×4 / ×6 `J1.1` (non connectée)
- **Constat :** La broche 8 du nœud est à la masse, mais elle arrive sur la broche 1 des cartes DATA, laissée libre exprès pour qu'un cordon droit n'y amène pas le 20–28 V. Le retour des ≈ 1,76 A maximum passe donc par les broches 2 et 5 seulement.
- **Conséquence :** Aucune en fonctionnement : deux contacts PH de 2 A suffisent. À garder en tête si la limite de courant du cordon est un jour relevée.

#### X4A-09 · DATA ×4 · Rien n'écrête le 5 V : une seule panne met le 20–28 V sur le hub et sur quatre cartes sous test

*Remarque · confirmé*

- **Où :** Rail `+5V` · `R52` (résistance haute du diviseur de contre-réaction) · `U13` · `design.py:920` (« no second protection here »). Même schéma sur la DATA ×6
- **Constat :** Un seul interrupteur sépare le 20–28 V du régulateur du hub (6,5 V maximum), des quatre TPS2553 (7 V) et des cartes sous test. Un joint ouvert sur `R52`, ou un transistor haut en court-circuit, amène la sortie à VIN. L'eFuse du nœud limite le courant, pas la tension.
- **Correction :** Choix à faire en connaissance de cause : un circuit d'écrêtage à thyristor sur le 5 V, ou une coupure de surtension avant les interrupteurs de port. Sinon, accepter le risque et l'écrire.

#### CP-3 · Caméra · Pas de résistance série sur MISO du côté où le signal est émis

*Remarque · à vérifier*

- **Où :** `MISO` : `J2.4` → `J1.4` en direct · côté nœud, `R33` 33 Ω
- **Constat :** Les résistances série de 33 Ω sont toutes sur le nœud. C'est le bon bout pour SCK, MOSI et CS, que le nœud émet, mais MISO est émis par la caméra : sa résistance se trouve à l'arrivée, après 50 cm de cordon non adapté.
- **Conséquence :** Dépassements possibles sur MISO à l'entrée du nœud. À 4 MHz cela passe en général sans erreur.
- **Correction :** Une empreinte 0603 en série sur MISO près de J2 (33–47 Ω, ou 0 Ω si l'oscilloscope montre que ce n'est pas nécessaire).

#### BN-10 · Nœud · Le chemin VRACK tient sur deux vias à chaque extrémité

*Remarque · confirmé*

- **Où :** `J1.1`, `J2.6` et languette de `Q1` : deux vias 0,6 / 0,3 mm chacun · bande VRACK sur In2, rétrécie à 2,5 mm vers x = 46,6
- **Constat :** La bande interne (3,8 mm, ≈ 22 mΩ) suffit pour les 1,6 A d'une rangée : 35 mV et 56 mW. Mais chaque connecteur n'y accède que par deux petits vias, alors que VIN après Q1 a reçu des pistes de 1,7 mm et des vias 0,8 / 0,4 mm.
- **Conséquence :** Pas de problème thermique. Un via fissuré double la charge de l'autre.
- **Correction :** Quatre vias 0,8 / 0,4 mm à chaque extrémité, ou un pont côté composants entre l'îlot de J1 et la languette de Q1.

#### PH-07 · Hub · L'émetteur-récepteur CAN est alimenté derrière une diode : 4,57 V au pire pour un seuil de sous-tension à 4,0–4,5 V

*Remarque · confirmé · connu*

- **Où :** `U6` broche 3 sur `+5V`, après `D4`/`D5`
- **Constat :** Pire cas : 5,10 V en sortie d'abaisseur, moins ≈ 0,5 V dans la diode pendant une salve Wi-Fi, moins la piste. Typiquement 4,8 V. Sur l'USB de console seul, le CAN peut fonctionner ou non, ce que la doc dit déjà.
- **Correction :** Prochaine révision : alimenter U6 depuis la sortie de l'abaisseur, avant la diode (5,10–5,39 V).

#### X4A-10 · DATA ×4 · Trois chemins d'alimentation sans redondance

*Remarque · confirmé*

- **Où :** `VIN` : une piste de 0,6 mm sur ≈ 125 mm de B.Cu · `+5V` : une bande de 4 mm sur In2 (12,3 mΩ) · un via par interrupteur de port
- **Constat :** VIN : ≈ 0,08 Ω, soit 0,12 V et 0,15 W au pire ; suffisant, mais 1,0 mm ne coûte rien sur B.Cu. Le 5 V de tous les ports traverse une bande de 4 mm de cuivre fin : 38 mV à 3,09 A. Au pire, VBUS à l'embase vaut 4,77 V, soit 20 mV au-dessus du minimum USB.
- **Correction :** Élargir VIN, doubler la bande 5 V par une bande sur B.Cu, mettre un second via par interrupteur.

#### X4B-07 · DATA ×4 · Les entrées de commande des CH446Q flottent jusqu'à la première écriture du nœud

*Remarque · confirmé · connu*

- **Où :** `U10` (TCA9534A) P0–P3 et P7 : DAT, CK, STB1, STB2, MARK · `R20` sur MX_RST
- **Constat :** Le TCA9534A démarre en entrées, sans tirage. Seul RST est tenu, à l'état qui garde tous les interrupteurs ouverts, donc rien ne peut se fermer. L'ordre des premières écritures compte : P0–P3 en sortie basse avant de relâcher RST.
- **Correction :** Vérifier que le test du pilote couvre cette première séquence. À une prochaine révision, quatre résistances de 100 kΩ à la masse suppriment la dépendance.

#### X6-12 · DATA ×6 · Deux rails 5 V séparés : une carte à deux prises USB branchée à cheval peut voir un port se couper

*Remarque · probable*

- **Où :** `+5V_A` (ports 1–3) et `+5V_B` (ports 4–6)
- **Constat :** Les deux rails peuvent différer de 0,28 V aux extrêmes. Une carte sous test qui relie les VBUS de ses deux prises, branchée sur un port de chaque groupe, réunit les rails ; le TPS2553-1 du rail le plus bas voit sa sortie au-dessus de son entrée et se verrouille. Rien n'est abîmé.
- **Correction :** Une ligne dans la doc utilisateur : mettre les deux câbles d'une telle carte dans le même groupe.

#### BN-11 · Nœud · États au reset : trois détails sans gravité

*Remarque · confirmé*

- **Où :** `SW3` → `SVC` → `U3.8` (IO15) · `LED_DIN` (IO38) · `CAN_TXD` (IO18)
- **Constat :**
  - L'interrupteur SERVICE relie IO15 directement au +3V3, et IO15 passe à l'état bas ≈ 60 µs à la mise sous tension : un bref court-circuit quand SERVICE est enclenché.
  - `LED_DIN` n'a pas de tirage : la LED peut afficher une couleur aléatoire jusqu'à la première écriture.
  - IO18 a aussi une impulsion parasite de ≈ 60 µs à chaque démarrage ; le dépôt la note déjà comme source possible d'une trame d'erreur CAN.

  Toutes les sorties qui comptent sont tenues par une résistance : eFuse, multiplexeurs, AUX, éclairage, CS de la caméra.
- **Correction :** 1 kΩ en série sur IO15 et 100 kΩ à la masse sur `LED_DIN` à la prochaine révision.

#### PH-08 · Hub · Les sorties de défaut des eFuses vont directement aux GPIO

*Remarque · probable*

- **Où :** `FLT_A–FLT_D` : broche 14 des eFuses → IO18, IO21, IO47, IO33 de `U4`, sans pièce en série
- **Constat :** IO18 a une impulsion parasite de ≈ 60 µs à la mise sous tension, alors que la sortie de défaut est à l'état bas tant que la rangée est coupée : 13 à 40 mA pendant 60 µs, sans gravité. Et la broche FLT (14) est voisine de OUT (15), à 0,25 mm : un pont de soudure mettrait VRACK sur un GPIO sans rien pour le limiter.
- **Correction :** Prochaine révision : 1 kΩ entre chaque sortie de défaut et son GPIO, comme pour BN-01.

#### X4A-11 · DATA ×4 · Du cuivre de signal passe dans la fente est du berceau

*Remarque · confirmé*

- **Où :** `UP_DN` sur F.Cu à x 94,15–94,85 sur 13 mm, avec son via · `HUB_1V8` jusqu'à x 95,3 · la fente prend x ≥ 94,5
- **Constat :** La zone interdite n'y vise que les pièces. Rien ne faillit électriquement, mais la ligne D− amont et le rail 1,8 V du hub se trouvent là où la carte glisse dans le berceau.
- **Conséquence :** Une rayure à travers le vernis expose une ligne USB ou le rail de cœur du hub.
- **Correction :** Décaler la paire amont de 0,6 mm vers l'ouest, ou étendre la zone interdite aux pistes autres que la masse.

#### X4B-08 · DATA ×4 · Mesure de VREF à travers 105 kΩ, sans condensateur à l'entrée du convertisseur

*Remarque · probable*

- **Où :** `R115–R415` (100 kΩ) vers GPIO40–43 · `R38`/`R39` vers GPIO44
- **Constat :** Le courant de fuite de broche spécifié (≤ 1 µA) donne jusqu'à ±0,1 V à la broche, soit ±0,2 V sur VREF. La décision « VREF non câblé » (0,19 V lu pour un seuil à 0,33 V) n'a alors que 0,03 V de marge. Sur une puce de révision A2, l'entrée numérique de GPIO40–45 doit rester désactivée (erratum E9).
- **Correction :** 10 à 100 nF sur chaque entrée à une prochaine révision ; en attendant, échantillonner lentement, écarter la première conversion et mettre de l'hystérésis sur le seuil.

#### X6-13 · DATA ×6 · Notes de conception et sérigraphie en désaccord avec la carte

*Remarque · confirmé*

- **Où :** `design.py:434`, `:478`, `:427`, `:907` · sérigraphie arrière « LEAD 20 V »
- **Constat :**
  - La limite du nœud est donnée à « ≈ 1,5 A » ; elle est de 1,76 A.
  - « AP2114H, SOT-223 on copper » : il n'y en a pas (X6-02).
  - La note de l'abaisseur cite encore l'inductance FXL0630, remplacée, et le hub à « 0,42 A at most » (la fiche donne 460 mA).
  - La sérigraphie « LEAD 20 V » : le même cordon porte 28 V sur un rack EPR.

#### BN-13 · Nœud · Comportements de l'eFuse à reprendre dans le micrologiciel

*Remarque · confirmé · connu*

- **Où :** `U9` (TPS26600), OVP à la masse
- **Constat :**
  - Seuil de surtension : 31–34 V à la montée, 28,5–31,5 V à la descente. Sur un bus EPR de 28 V (jusqu'à 29,4 V), un U9 déclenché par une surtension peut ne pas se refermer seul.
  - À l'arrêt, la sortie fuit jusqu'à 12 µA dans les ≈ 830 kΩ de l'INA226 : `DATA_VIN` peut afficher plusieurs volts sans rien de branché.
  - Dissipation à 1,76 A : 0,47 W typique, 0,78 W au pire, soit 18 à 30 °C d'échauffement.
- **Correction :** Signaler le premier cas depuis le nœud, comme le fait déjà le hub.

#### PH-09 · Hub · La résistance de mesure de courant dépasse de peu le maximum de la formule TI

*Remarque · confirmé*

- **Où :** `R31–R34` (18 kΩ)
- **Constat :** L'équation 5 de la fiche donne 17,7 kΩ au maximum, avec un facteur 1,8 qui couvre la zone de déclenchement rapide. En régime établi, la lecture reste dans la plage du convertisseur.
- **Conséquence :** Aucune pour les lectures du micrologiciel.

#### X4A-12 · DATA ×4 · Petits points déjà connus ou cosmétiques

*Remarque · confirmé · connu*

- **Où :** Hub, `Q1`/`Q2`, `U4`, `BUCK_CB`
- **Constat :**
  - Pas de condensateur de réserve près du hub : le plus proche est à ≈ 90 mm, au régulateur. Un 4,7 µF 0402 à côté de `C13` coûte une pose.
  - MOSFET d'isolation I²C 2N7002 sur une grille à 3,3 V : voir X6-10.
  - La protection `U4` est sur une dérivation de 5,7 mm, pas en série. Acceptable sur un cordon interne.
  - Piste du condensateur d'amorçage : 0,127 mm, à passer à 0,25 mm.
  - 262 mm de pistes à 0,095 mm, au minimum de JLC.

#### X4B-09 · DATA ×4 · Le verrou « VREF sous 0,65 V : interrupteurs ouverts » n'existe pas encore

*Remarque · confirmé · connu*

- **Où :** `design.py:634–640` · `docs/electronics.md`, ligne « Pins »
- **Constat :** VREF est mesuré par le coprocesseur, mais les interrupteurs sont fermés par le nœud. La règle suppose un compte rendu du coprocesseur vers le nœud que l'image d'analyseur d'origine n'a pas. La doc la décrit pourtant comme acquise.
- **Conséquence :** Un VREF non câblé n'est pas isolé : les niveaux bas passent, les hauts sont écrêtés vers 0,4 V. Sans danger.
- **Correction :** Le dire dans les limites affichées à l'utilisateur tant que notre image n'existe pas.

#### X6-14 · DATA ×6 · Observations d'implantation sans action immédiate

*Remarque · confirmé*

- **Où :** Paires USB des ports · pistes de 0,09 mm · `D101–D601`
- **Constat :**
  - D− est 2,9 à 4,15 mm plus long que D+ sur chaque port (20–28 ps) : sans effet à 480 Mbit/s.
  - 116 mm de pistes de 0,09–0,095 mm avec 0,1 mm d'isolement : le minimum annoncé par JLC en 4 couches. Cela se fabrique ; le rendement est meilleur à 0,127 mm là où il y a la place.
  - Les LED de VBUS se trouvent derrière la barrette du berceau : visibles seulement par le dessus. À confirmer côté mécanique si elles doivent se voir.
  - Le point de test `TP42` (VIN, 20–28 V) est à 1,5 mm d'un point de masse : sonder avec précaution.

#### BN-14 · Nœud · Fabrication : inductance sans empreinte JLC, deux libellés de sérigraphie

*Remarque · à vérifier*

- **Où :** `L1` (IHLP2525CZ, C48009678) · sérigraphie de la face arrière
- **Constat :** La fiche JLC de C48009678 n'a ni empreinte ni fiche technique : la pose de L1 ne peut pas être comparée au dessin de JLC (la pièce n'est pas polarisée, et la plage a été vérifiée à la main dans `catalog.py`). C553961 est la même inductance sur une autre bobine et en a une. Sur la face arrière, les noms « CS » et « SCL » se touchent et « POS OUT » est coupé dans le rendu.
- **Correction :** Regarder L1 dans l'aperçu JLC ; écarter les deux libellés.

#### PH-10 · Hub · L'inductance de l'abaisseur n'a pas d'empreinte chez JLC et son stock baisse

*Remarque · confirmé*

- **Où :** `L1` (IHLP2525CZEK4R7M01, C48009678) · même référence sur le nœud (`L1`) et la DATA ×6 (`L2`, `L3`)
- **Constat :** JLC liste C48009678 sans empreinte ni fiche, avec 690 pièces. C553961 est la même inductance Vishay sur une autre bobine, avec empreinte et 4 222 pièces en stock.
- **Correction :** Commander avec C553961, sauf si JLC confirme qu'il pose C48009678.

#### X4B-10 · DATA ×4 · Ce que supporte une broche P mal câblée : 5,5 V oui, 12 V ou une tension négative non

*Remarque · probable*

- **Où :** Connecteurs `J102–J402`, broches P1–P8 et VREF · H5VU25UC, LSF0108
- **Constat :** Jusqu'à 5,5 V, tout tient (tension de service 5 V, claquage ≥ 6 V, LSF0108 ≤ 7 V). Un rail 12 V sur une broche fait conduire le réseau de protection jusqu'à sa destruction, puis expose le LSF0108 derrière 100 Ω. Une tension négative est écrêtée sans limitation de courant.
- **Correction :** Sérigraphier « MAX 5 V » près des connecteurs et l'écrire dans la règle VREF.

#### PH-11 · Hub · Le fichier de placement est spécifique à JLC

*Remarque · à vérifier*

- **Où :** `fab/*-cpl-jlcpcb.csv` sur toutes les cartes · commentaires de `design.py` et `silk.py` mentionnant NextPCB
- **Constat :** Le seul fichier de placement publié porte les corrections de la bibliothèque JLC : 270° ou 180° sur dix-huit pièces du hub, des décalages d'origine sur d'autres. Des commentaires récents laissent penser que les prototypes iront chez NextPCB.
- **Conséquence :** Un autre assembleur, qui lit les rotations à la convention de KiCad, tournerait ces pièces d'un quart ou d'un demi-tour.
- **Correction :** Pour tout autre assembleur que JLC, exporter le fichier de positions non corrigé et le dire dans la commande.

#### PH-12 · Hub · Petites observations d'implantation

*Remarque · confirmé*

- **Où :** Îlot d'entrée de l'abaisseur · `C8`, `C9`, `C10` · `U1`
- **Constat :**
  - Le routeur a donné une seconde arrivée à l'îlot d'entrée de l'abaisseur ; elle porte environ deux tiers du courant, à la place de la piste dessinée pour cela. Sans conséquence à 0,7 A.
  - Le condensateur de réserve `C8` et deux 10 µF rejoignent le plan par un seul via de 0,6 / 0,3 mm chacun.
  - La seule masse du CH224A est sa pastille centrale, avec un via : il doit être refondu, pas soudé à la main par les broches.
  - Les LED vertes reçoivent ≈ 1 mA (≈ 3 mcd) : à regarder en lumière ambiante sur la première carte.

## Câbles entre cartes

Relevé sur les cinq PCB routés (réseau de chaque pastille), pas sur la documentation.  Les trois câbles sont des cordons JST PH tout faits de type « same direction » : la broche n d'un bout arrive sur la broche N + 1 − n de l'autre.

**Câble de rangée, PH 6**

| Hub J2–J5, nœud J2 | Signal | Nœud J1 |
|---|---|---|
| 1 | POS | 6 |
| 2 | GND | 5 |
| 3 | CAN_L | 4 |
| 4 | CAN_H | 3 |
| 5 | GND | 2 |
| 6 | VRACK 20–28 V | 1 |

**Cordon DATA, PH 8**

| Nœud J7 | Signal | DATA ×4 / ×6 J1 |
|---|---|---|
| 1 | DATA_VIN 20–28 V | 8 |
| 2 | GND | 7 |
| 3 | D+ | 6 |
| 4 | D− | 5 |
| 5 | GND | 4 |
| 6 | SDA | 3 |
| 7 | SCL | 2 |
| 8 | GND côté nœud | 1, libre côté carte DATA (SYS-4) |

**Cordon caméra, PH 8**

| Nœud J6 | Signal | Caméra J1 |
|---|---|---|
| 1 | GND | 8 |
| 2 | SCK | 7 |
| 3 | CAM_5V | 6 |
| 4 | MOSI | 5 |
| 5 | MISO | 4 |
| 6 | LED_K | 3 |
| 7 | CS | 2 |
| 8 | GND | 1 |

**Bus I²C partagé par le cordon DATA**

| Carte | Circuit | Adresses |
|---|---|---|
| Nœud | INA226 du cordon DATA | 0x40 |
| DATA ×6 | TCA9535 · six INA226 | 0x20 · 0x41 0x43 0x44 0x45 0x47 0x4C |
| DATA ×4 | deux TCA6408A · TCA9534A · quatre INA226 | 0x20 0x21 · 0x38 · 0x41 0x43 0x44 0x45 |

Aucune collision : une baie ne reçoit qu'une carte DATA à la fois, et aucune n'occupe le 0x40 du nœud.

## Détail par carte

### Hub d'alimentation

Entrée USB-C PD (CH224A, 20 V ; 28 V en option, verrouillé dans le micrologiciel), quatre sorties de rangée protégées par eFuse TPS26600, contrôleur ESP32-S3-MINI-1, CAN. Aucun constat critique ni majeur : tous les brochages, valeurs et tensions maximales vérifiés sont justes, et le chemin de puissance tient ses 5 A. Quatre points mineurs méritent une retouche avant commande ; deux risques connus de l'étage PD ne concernent que des chargeurs pointilleux ou l'option 28 V.

Vérifié et trouvé correct :

- ERC et DRC : 0 erreur, 0 avertissement, 0 piste non connectée.
- CH224A (ESSOP-10) : brochage, VBUS relié à VHV comme demandé, CC1/CC2, CFG1, PG.
- TPS26600 (×4, HTSSOP-16) : brochage ; limite 12 / 7,5 kΩ = 1,60 A (1,52–1,68 A) ; démarrage progressif 17 ms à 20 V, soit 0,52 A dans les 450 µF d'une rangée ; UVLO 15 V, OVP 31–34 V.
- Rangées coupées sans micrologiciel : IO14–17 sans tirage au reset, SHDN à 0,1 V au repos (seuil 0,55 V) et 1,65 V en marche (≥ 1 V requis).
- Mesure de courant : 1,40 V/A, 2,25 V à 1,6 A et 2,60 V au pire, dans la plage 0–2,9 V du convertisseur de l'ESP32, sur ADC1.
- Abaisseur LMR51625 et régulateur AP2112K : brochages ; 5,24 V ; inductance 75 V ; +5V entre 4,6 et 5,05 V après la diode ; entrée du régulateur ≥ 3,9 V sur l'USB seul.
- ESP32-S3-MINI-1 : pastilles 1 à 45 conformes ; IO19 = D−, IO20 = D+ ; broches de configuration IO0, IO3, IO45, IO46 correctes.
- CAN : TJA1462AT (variante avec VIO), terminaisons 2 × (56 + 56 Ω) = 56 Ω, mode normal au reset, TXD récessif au reset ; PESD2CAN.
- POS avec VRACK dessus par erreur : (29,4 − 3,6) V / 10 kΩ = 2,6 mA, sans danger.
- Tenue en tension : tout ce qui est sur VRACK supporte l'écrêtage à 48,4 V de la TVS (eFuses 62 V, abaisseur 63 V, condensateurs 50 V), sauf le CH224A (PH-06).
- Chemin de puissance à 5 A : 53–59 mV de l'entrée à l'eFuse la plus éloignée, 0,2 W dans le plan ; cuivre le plus étroit 7,3 mm. Sortie de rangée : 10 mΩ, 16 mV à 1,6 A.
- Connecteurs de rangée J2–J5 : broche 1 conforme au plan JST, cohérents avec l'entrée des nœuds.
- Corrections de rotation JLC : toutes recalculées à l'identique, sauf celle qui manque pour D41–D44 (PH-01). Polarités de D1, D4, D5, C8 et des LED vérifiées.
- En mode téléchargement, la ROM force IO40 à l'état haut : ici c'est la ligne SCL du CH224A, que rien ne tire à la masse. Pas de conflit comparable à celui du nœud (BN-01).

Non vérifié :

- Fiche CH224 V2.1, la référence du dépôt : seule la V2.0 était accessible. L'adresse I²C (0x22 ou 0x23) et la lecture des offres du chargeur restent ouvertes, comme dans la revue de schéma du dépôt.
- Capacité de la sortie PG du CH224A, fiche de la LED rouge.
- Tenue mécanique dans le boîtier d'alimentation, au-delà de l'entretoise de PH-03.
- Tout ce qui demande un banc : comportement des chargeurs à l'insertion, échauffement boîtier fermé, CEM.

### Nœud de baie

Un par baie : ESP32-S3-WROOM-1, abaisseur 5 V, eFuse TPS26600 et mesure INA226 sur le cordon DATA (20–28 V), multiplexeurs USB, CAN, caméra, AUX. Aucune erreur de brochage, de polarité ni de connexion. Un constat majeur (BN-01) se corrige avec une résistance ; le reste touche à la robustesse sur court-circuit, au routage près de la paire USB et à la documentation, qui décrit encore l'ancien interrupteur 5 V.

Vérifié et trouvé correct :

- ERC et DRC : 0 erreur, 0 avertissement, 0 piste non connectée.
- ESP32-S3-WROOM-1-N8R8 : les 41 pastilles conformes à la fiche du module ; IO35–37 (PSRAM) et IO3/45/46 libres ; IO19 = D−, IO20 = D+ ; `check_pinmap.py` passe (27 GPIO).
- TPS26600 (U9) : brochage HTSSOP-16 conforme ; limite 12 / 6,8 kΩ = 1,76 A ± 5 % ; démarrage progressif 3,8 ms à 20 V ; UVLO, OVP et MODE à la masse comme prévu ; coupé par défaut (R17).
- INA226 (U10) : brochage, adresse 0x40, tension de bus ≤ 34 V derrière la protection de surtension, sous les 36 V admis.
- Abaisseur LMR51625 : brochage, 0,8 V × (1 + 100/18) = 5,24 V, seuils de démarrage 13,5 V / 10,8 V, ondulation 0,82 A crête à crête à 28 V, condensateurs 50 V sur le bus, boucle chaude compacte.
- Protection d'entrée : sens de Q1 (diode de corps de VRACK vers VIN), zener de grille, TVS écrêtant à 53 V sous les 62–63 V des circuits en aval, polarités de D1, D2, D8 et C1.
- Multiplexeurs FSUSB42 et porte OU : table de vérité correcte dans tous les modes ; pas de dérivation sur la paire en mode classique.
- Paire USB haute vitesse : 0,25 / 0,15 mm sur 0,21 mm de préimprégné, ≈ 90 Ω ; D+ 78,1 mm, D− 74,9 mm plus deux vias ; plan de masse continu dessous.
- USBLC6 (×4), TJA1462AT (d'après le symbole LCSC), PESD2CAN, BAT54S, 2N7002, AO3400A, WS2812B-2020, interrupteur SERVICE : brochages conformes.
- POS avec VRACK dessus par erreur : (28 − 3,6) V / 10 kΩ = 2,4 mA, sans danger.
- Bande d'antenne : aucun cuivre sur aucune couche ; trous de fixation dégagés.
- Placement JLC vérifié pour C1, D1, D2, D4, J3, J7, Q1–Q4, U2, U9.

Non vérifié :

- Fiche technique NXP du TJA1462 : inaccessible pendant la revue ; ses limites électriques reposent sur l'audit antérieur du dépôt.
- Toute mesure : températures, chute de la rangée au branchement (BN-04), diaphonie (BN-05, BN-09), œil USB à travers les multiplexeurs et le cordon.
- Aperçu de placement JLC.

### Carte caméra

Cordon PH 8 depuis le nœud, connecteur de l'Arducam Mega, régulateur 3,3 V, quatre LED blanches. Carte simple et saine : aucun défaut bloquant, trois points à reprendre si la carte est retouchée avant commande.

Vérifié et trouvé correct :

- ERC et DRC : 0 erreur, 0 avertissement, 0 piste non connectée.
- J1 est bien le miroir du J6 du nœud pour un cordon « same direction » (broche n ↔ 9 − n), relevé sur les deux PCB routés.
- AP2114H-3.3 en SOT-223 : 1 GND, 2 et languette VOUT, 3 VIN, conforme au symbole JLC de C150716 et au câblage du PCB.
- LED XL-2835UWC-02 : la cathode est la grande plage (pastille 1), sur l'empreinte KiCad comme sur celle de JLC ; LED_K est bien sur la pastille 1.
- Courant des LED : (5,1 V − 2,9 V) / 100 Ω ≈ 22 mA par LED, ≈ 48 mW dans une résistance 0805 de 125 mW.
- Condensateurs C1 (10 µF) et C2 (22 µF) en 25 V sur des rails de 5 V et 3,3 V.
- J2 suit l'ordre du connecteur de la Mega (VCC, GND, SCK, MISO, MOSI, CS), VCC sur la broche 1.
- Largeurs de piste : 0,4 mm sur CAM_5V (≤ 0,42 A), 0,3 mm sur LED_K (≤ 0,1 A).

Non vérifié :

- Rotations et décalages du fichier de placement JLC : ils se confirment dans l'aperçu de placement de JLC à la commande (déjà noté « to confirm » dans la doc).
- Tenue mécanique dans le boîtier imprimé et position des LED par rapport à l'objectif.

### DATA ×4

Carte de tiroir pour quatre cartes sous test, en deux assemblages sur un même panneau : la base (hub USB2517I, quatre USB-C commutés et mesurés, abaisseur LMR51635 depuis le 20–28 V du cordon) et la logique (matrice CH446Q, RP2350B). Relue en deux moitiés : constats **X4A** pour la base, **X4B** pour la logique. Aucune erreur de brochage, de connexion ni de valeur dans l'une ou l'autre. Les points à traiter avant commande : la rupture de stock de l'interrupteur de port (SYS-6), la broche 28 V soudée à la main tout près du hub (X4A-01) et la marge thermique de l'abaisseur à pleine charge (X4A-02).

Vérifié et trouvé correct :

- ERC : 0 erreur. DRC avec parité : 0 erreur, 0 piste non connectée ; les 7 avertissements d'empreinte (U2, U6, U11, U107–U407) ne portent que sur le chemin du modèle 3D et des réglages de zone, pastilles identiques.
- **Base :** J1 aujourd'hui = 1 libre · 2 SCL · 3 SDA · 4 GND · 5 D− · 6 D+ · 7 GND · 8 VIN, cohérent broche à broche avec le J7 du nœud ; empreinte correctement retournée en face arrière.
- LMR51635 (U13) : brochage ; 0,8 V × (1 + 100/18,7) = 5,08 V ; courant crête 3,90–3,95 A au pire pour une limite minimale de 4,2 A ; condensateurs d'entrée 50 V ; inductance IHLP2525CZ 3,3 µH (75 V).
- Démarrage : < 0,45 A pendant la rampe de l'eFuse du nœud, pour une limite de 1,67 A. Puissance d'entrée au pire : 0,92 A à 20 V, 1,22 A à 15 V.
- USB2517I : les 64 broches contre la table Microchip ; CFG_SEL = 110 ; toutes les broches de configuration tirées ; quartz 24 MHz avec 2 × 33 pF et 1 MΩ ; pastille centrale à neuf vias, pâte en 16 fenêtres.
- TPS2553-1 (×4), INA226 (0x41, 0x43, 0x44, 0x45), TCA6408A (0x20, 0x21), USBLC6, MAX809S, AP2114H, 2N7002 : brochages et adresses conformes.
- Embases USB-C GCT USB4145 : rangées A et B, CC, D+/D−, VBUS conformes au plan GCT.
- Paires USB : ≈ 92 Ω calculés (88–90 Ω avec le vernis) ; les quatre paires de port au-dessus d'un plan de masse continu sur toute leur longueur (50 à 98,5 mm), sans via ; écart D+/D− ≤ 0,82 mm.
- Nomenclature et placement : 237 pièces posées sur la logique, 138 sur la base, 99 non montées, aucune incohérence de référence LCSC ; aucune fonction de la base ne dépend d'une pièce non montée.
- Corrections de rotation JLC de cette moitié recalculées à partir des empreintes JLC : toutes justes.
- Panneau : les languettes démarrent hors des extrémités de 5,5 mm ; les condensateurs proches sont parallèles au bord. À séparer à la pince, pas en pliant.
- Corrections X1–X11 de la revue d'assemblage du dépôt et corrections de l'audit des fiches : toutes présentes dans la conception d'aujourd'hui.
- **Moitié logique :** RP2350B, les 81 pastilles comparées à la fiche technique Raspberry Pi (Fig. 3, Table 1674) et au symbole JLC : toutes sur le bon réseau.
- CH446Q (table des broches WCH v1D), TPS60400, TCA9534A (0x38, sans collision), LSF0108 : brochages et alimentations ±5 V conformes.
- Régulateur de cœur du RP2350B : schéma et cuivre conformes aux figures 25 et 26 de Raspberry Pi, tournés de 180° avec la puce ; aucun cuivre sous LX.
- Démarrage sans flash : QSPI_SS et SD1 sélectionnent bien le chargeur USB ; les broches QSPI libres ont leurs tirages internes.
- Réseaux de protection H5VU25UC : E/S sur 1, 2, 4, 5 et masse sur 8 seulement ; les paires de pastilles reliées donnent un vrai passage traversant, sans dérivation. Le retour de masse passe par la barre centrale de l'empreinte (≈ 2,3 mm), acceptable.
- Connecteurs 2 × 6 : rangée haute VREF · P1–P4 · BOOT, rangée basse GND · P5–P8 · RST, identique sur le PCB, la sérigraphie et la doc.
- Table P → X → bus : la doc, le devicetree du micrologiciel et le PCB concordent.
- Diaphonie entre voies de l'analyseur : plus long parcours parallèle 11,9 mm, de l'ordre de 10 mV. Sans effet.
- Port 5 du hub vers le coprocesseur : D+ sur D+, D− sur D−, 27 Ω en série.
- Variante de base : aucune pièce montée ne se trouve sur un réseau réservé à la logique.

Non vérifié :

- Températures (X4A-02 et régulateur 3,3 V) : estimées, à mesurer tiroir fermé.
- Temps de décroissance des rails (X4A-03) : estimé d'après les courants de repos.
- Fiches Microchip et ST d'origine inaccessibles : lecture faite sur les copies LCSC des mêmes documents.
- Comportements à mesurer sur table côté logique : résistance passante des CH446Q à ±5 V, fenêtre de coupure (X4B-01), niveau de repos des bus (X4B-02).
- Image d'analyseur d'origine sur RP2350B (tirages, usage des GPIO) : non ouverte.
- Aperçu de placement JLC, Gerber du panneau.

### DATA ×6

Carte de tiroir par défaut : six USB-C source, deux abaisseurs LMR51625 indépendants depuis le 20–28 V du cordon (ports 1–3 d'un côté, ports 4–6 et le 3,3 V de l'autre), hub USB2517I, un interrupteur et un INA226 par port. C'est la carte la plus récente et la seule sans revue antérieure. Tous les brochages vérifiés sont justes, y compris J1 contre le cordon croisé et le sens des embases USB-C. Deux constats majeurs : une rotation manquante dans le fichier de placement (X6-01, une ligne à ajouter) et un régulateur 3,3 V sans cuivre de dissipation (X6-02). S'y ajoute une rupture de stock (SYS-6).

Vérifié et trouvé correct :

- ERC : 0 erreur. DRC avec parité : 0 erreur, 0 piste non connectée ; le seul avertissement d'empreinte (U2) ne porte que sur le chemin du modèle 3D, pastilles identiques.
- J1 contre le cordon : VIN en broche 8, D+ en 6 vers la broche 59 du hub, D− en 5 vers la 58. Un cordon droit met VIN sur la broche libre et n'alimente rien.
- LMR51625 (U13, U14) : brochage, 63 V maximum absolu, seuils de démarrage 13,5 V / 10,8 V, condensateurs d'entrée 50 V, boucle chaude compacte.
- Budget d'entrée : 1,24 A à 20 V tous ports à leur limite, 1,63 A à 15 V, pour une limite du nœud de 1,67–1,85 A. Le démarrage tire ≈ 0,4 A : il ne peut pas déclencher l'eFuse du nœud.
- USB2517I : les 64 broches contre la fiche Microchip ; CFG_SEL = 110 (configuration interne, sans inversion de ports) ; ports DN1–5 vers USB-C 2–6 et DN6 vers USB-C 1, comme la doc.
- TPS2553-1 : brochage et limite 524 / 577 / 638 mA avec 45,3 kΩ ; coupé par défaut.
- INA226 : adresses 0x41, 0x43, 0x44, 0x45, 0x47, 0x4C lues sur les pastilles, sans collision avec 0x40 (nœud) ni 0x20 (TCA9535).
- Embases USB-C verticales GCT USB4145 : rangées A et B, CC1/CC2, D+/D−, VBUS conformes au plan GCT ; USBLC6 en passage traversant.
- Isolation I²C : sens des MOSFET correct, la diode de corps bloque carte éteinte ; le nœud ne peut pas réalimenter une carte éteinte.
- Paires USB : chacune au-dessus d'un plan de masse continu, aucune ne traverse une coupure de plan ; ≈ 90 Ω.
- Zones interdites du berceau : respectées (soudure la plus proche à x = 5,95 et 93,90 pour des bandes finissant à 5,5 et 94,5).
- Corrections reprises de l'audit de la DATA ×4 : superviseur de reset, 1 MΩ sur le quartz, 4,7 µF sur le 1,8 V, CFG_SEL 110. Deux ne l'ont pas été : le cuivre du régulateur (X6-02) et le diviseur 18,7 kΩ (X6-07).

Non vérifié :

- Températures : estimées à partir des résistances thermiques des fiches, rien n'a été mesuré ni simulé.
- Stabilité de boucle des abaisseurs, CEM, contenu de l'archive Gerber.
- Fiches non rouvertes pour cette carte : INA226, USBLC6, MAX809S, H5VU25UC, 2N7002, quartz (les réseaux concordent avec l'audit de la DATA ×4).
- Mécanique au-delà des zones interdites : C60 et les embases contre le capot du tiroir.

### Ensemble du rack

Constats qui tiennent à l'assemblage des cartes : câbles, protections en série, documentation commune.

Vérifié et trouvé correct :

- Câble de rangée (PH 6), cordon DATA (PH 8) et cordon caméra (PH 8) : chaque signal arrive sur la bonne broche, relevé sur les PCB routés.
- Erreurs de branchement passées en revue : cordon caméra dans la prise DATA, cordon DATA dans la prise caméra, cordon droit au lieu de croisé. Aucune ne met le 20–28 V sur une broche de signal.

Non vérifié :

- Budget de puissance complet et comportement du micrologiciel de délestage.

## Méthode et limites

**Ce qui a été fait**

- ERC et DRC de KiCad 10 (image `kicad/kicad:10.0-full`) relancés sur les cinq cartes, avec parité schéma/PCB et remplissage des zones : 0 erreur, 0 piste non connectée ; seuls des avertissements `lib_footprint_mismatch` sur la DATA ×4 (7) et la DATA ×6 (1), sans effet (chemin du modèle 3D).
- Extraction de la liste des réseaux, des positions, des largeurs de piste, des vias et des zones depuis chaque `.kicad_pcb` routé.
- Lecture de `design.py`, la source des schémas, et comparaison avec le PCB et la documentation.
- Brochages et empreintes comparés aux fiches techniques et aux symboles et empreintes JLC des références LCSC.
- Contrôle croisé des connecteurs entre cartes.
- Une relecture indépendante par carte (deux pour la DATA ×4), puis une seconde vérification des constats majeurs et des principaux mineurs : réseau sur le PCB, géométrie mesurée, fiches Espressif et TI, empreintes et stock JLC consultés le 2026-11-09.

**Limites**

- Aucune carte n'est fabriquée : rien n'a été mesuré.  Les constats « probable » ou « à vérifier » demandent une mesure ou une relecture de fiche technique.
- Les rotations d'un fichier de placement ne se confirment que dans l'aperçu de l'assembleur.
- Le micrologiciel et la mécanique imprimée sont hors du périmètre, sauf là où ils conditionnent une carte.
- Deux constats de la DATA ×4 annoncés majeurs par la relecture (X4A-01, X4A-02) sont classés mineurs ici : le premier est un risque d'assemblage, le second ne joue qu'à la charge maximale déclarée.
- Fiches non accessibles pendant la revue : NXP TJA1462 pour le nœud, CH224 V2.1, originaux Microchip et ST (copies LCSC lues à la place).

**Échelle de gravité**

- **Critique :** la carte ne fonctionne pas, s'abîme, ou n'est pas fabricable telle quelle.
- **Majeur :** une fonction échoue ou se dégrade en conditions réalistes.
- **Mineur :** marge, robustesse, gêne à l'assemblage.
- **Remarque :** observation ou suggestion.
