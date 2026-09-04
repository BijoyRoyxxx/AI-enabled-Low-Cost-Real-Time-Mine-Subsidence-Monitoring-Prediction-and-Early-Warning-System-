import matplotlib.pyplot as plt
import networkx as nx

# Initialize directed graph
G = nx.DiGraph()

# Define layers / nodes
layers = {
    "Hardware Tier": ["ESP8266/ESP32 Nodes", "MPU-6050 Sensors", "LoRa / nRF24L01 Mesh"],
    "Backend & AI": ["Python Engine", "Pandas Data Prep", "Scikit-Learn (Isolation Forest)"],
    "Dashboard & UI": ["Streamlit Framework", "Plotly Charts", "Folium GIS Maps"],
    "Deployment": ["GitHub Version Control", "Streamlit Community Cloud", "Live SCADA URL"]
}

# Add nodes and edges to build a clean flowchart
current_parent = None
for layer_name, components in layers.items():
    for comp in components:
        G.add_node(comp, layer=layer_name)
        if current_parent:
            G.add_edge(current_parent, comp)
        current_parent = comp

# Set up the plot layout
plt.figure(figsize=(10, 8), facecolor="#0b0f19")
ax = plt.gca()
ax.set_facecolor("#0b0f19")

pos = nx.spring_layout(G, seed=42)

# Draw graph elements with industrial styling
nx.draw_networkx_nodes(G, pos, node_size=3000, node_color="#1f2937", edgecolors="#00ffff", linewidths=2)
nx.draw_networkx_edges(G, pos, edge_color="#38bdf8", width=2, arrowsize=20)
nx.draw_networkx_labels(G, pos, font_size=9, font_color="white", font_weight="bold")

plt.title("GEO-SHIELD SYSTEM ARCHITECTURE & TECH STACK", color="white", fontsize=14, fontweight="bold", pad=20)
plt.axis("off")

# Save directly as PNG
plt.savefig("architecture_diagram.png", format="png", dpi=300, bbox_inches="tight", facecolor="#0b0f19")
print("Successfully generated architecture_diagram.png in your project folder!")