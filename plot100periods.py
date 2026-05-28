import pandas as pd
import matplotlib.pyplot as plt

# 1. Chargement des données du fichier CSV brute
try:
    df = pd.read_csv("raw_signals_capture.csv")
except FileNotFoundError:
    print("Erreur : Le fichier 'raw_signals_capture.csv' est introuvable.")
    exit()

# 2. Identification des fronts pour isoler les 10 premières périodes
# Une période complète ici va d'un front montant au front montant suivant.
df['Clock_Edge'] = df['DIO2_Clock'].diff()
rising_edges = df[df['Clock_Edge'] == 1].index.tolist()

if len(rising_edges) < 11:
    print(f"Attention : Seulement {len(rising_edges)} périodes trouvées. Affichage de la totalité du fichier.")
    df_slice = df
else:
    # On découpe le DataFrame du début jusqu'au 11ème front montant (ce qui fait exactement 10 périodes)
    index_fin = rising_edges[10]
    df_slice = df.iloc[:index_fin + 50]  # On ajoute une petite marge de 50 points pour la lisibilité

# 3. Extraction des axes
time_ns = df_slice['Time_ns']
dio0 = df_slice['DIO0_Data']
dio1 = df_slice['DIO1_Comp']
clock = df_slice['DIO2_Clock']

# 4. Génération du graphique
plt.figure(figsize=(14, 7))

# Tracé des signaux avec un décalage vertical pour créer les canaux de l'analyseur
plt.step(time_ns, clock + 2.5, where='mid', color='r', linewidth=2, label='DIO2 (Clock)')
plt.step(time_ns, dio0 + 1.2, where='mid', color='b', linewidth=2, label='DIO0 (Data)')
plt.step(time_ns, dio1, where='mid', color='g', linewidth=2, label='DIO1 (Comp)')

# Configuration des axes et du style
plt.title('Analyseur Logique : Zoom sur les 10 premières périodes de l\'Horloge', fontsize=14, fontweight='bold')
plt.xlabel('Temps (Nanosecondes)', fontsize=12)
plt.ylabel('Signaux Électriques', fontsize=12)

# Placement des étiquettes en face de chaque ligne
plt.yticks([0.5, 1.7, 3.0], ['DIO 1 (Comp)', 'DIO 0 (Data)', 'DIO 2 (Clock)'], fontsize=11)
plt.grid(True, linestyle=':', alpha=0.7)
plt.legend(loc='upper right', fontsize=10)

# Optionnel : Marquer les fronts montants détectés pour vérification visuelle
for edge_idx in rising_edges[:10]:
    plt.axvline(x=df.iloc[edge_idx]['Time_ns'], color='purple', linestyle='--', alpha=0.4)

plt.tight_layout()
plt.show()