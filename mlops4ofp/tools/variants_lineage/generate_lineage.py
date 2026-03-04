# generate_html.py
import os
import yaml
import json
from config import BASE_DIR, PHASES, PHASE_COLORS, CSS_STYLES, DST_HTML_DIR, OUTPUT_FILENAME

def load_yaml(filepath):
    if not os.path.exists(filepath):
        return {}
    with open(filepath, 'r') as file:
        return yaml.safe_load(file) or {}

def build_html_dashboard():
    html_columns = []
    edges_js = []
    configs_data = {}

    for i, phase in enumerate(PHASES):
        phase_name = phase["name"]
        ctrl_variants = phase.get("ctrl_variants", "variants.yaml")
        variants_file = os.path.join(BASE_DIR, phase_name, ctrl_variants)
        variants_data = load_yaml(variants_file)
        
        colors = PHASE_COLORS.get(phase_name, PHASE_COLORS["default"])
        
        column_html = f'<div class="phase-column" id="col_{phase_name}" style="border-top-color: {colors["border"]}">'
        column_html += f'<div class="phase-title">{phase_name}</div>'

        if 'variants' in variants_data:
            for variant_id, _ in variants_data['variants'].items():
                node_id = f"{phase_name}_{variant_id}"
                
                card_style = f"background-color: {colors['bg']}; border-color: {colors['border']}; color: {colors['text']};"
                column_html += f'<div class="variant-card" id="{node_id}" style="{card_style}" onclick="showConfig(\'{node_id}\')">{variant_id}</div>'
                
                params_path = os.path.join(BASE_DIR, phase_name, variant_id, "params.yaml")
                params = load_yaml(params_path)
                configs_data[node_id] = params
                
                parents = []
                for parent_key in phase["parent_keys"]:
                    if parent_key in params:
                        val = params[parent_key]
                        if isinstance(val, list): parents.extend(val)
                        elif val is not None: parents.append(val)
                
                if parents and i > 0:
                    prev_phase_name = PHASES[i - 1]["name"]
                    for p in parents:
                        parent_node_id = f"{prev_phase_name}_{p}"
                        
                        edges_js.append(f"""
                            var startNode = document.getElementById('{parent_node_id}');
                            var endNode = document.getElementById('{node_id}');
                            if (startNode && endNode) {{
                                var line = new LeaderLine(startNode, endNode, {{ 
                                    color: '#adb5bd', 
                                    size: 2, 
                                    path: 'fluid', 
                                    startSocket: 'right', 
                                    endSocket: 'left'
                                }});
                                lines.push(line);
                            }}
                        """)
        
        column_html += '</div>'
        html_columns.append(column_html)

    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>MLOps Pipeline Lineage</title>
        <style>{CSS_STYLES}</style>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/leader-line/1.0.7/leader-line.min.js"></script>
    </head>
    <body>
        <div class="pipeline-container" id="pipeline-container">
            {''.join(html_columns)}
        </div>

        <div id="config-panel">
            <span class="close-btn" onclick="closeConfig()">Cerrar ✕</span>
            <h2 id="config-title">Configuración</h2>
            <pre id="config-content">Selecciona una variante...</pre>
        </div>

        <script>
            let lines = [];
            const variantConfigs = {json.dumps(configs_data)};

            function showConfig(nodeId) {{
                document.getElementById('config-panel').classList.add('open');
                document.getElementById('config-title').innerText = "Variante: " + nodeId;
                document.getElementById('config-content').innerText = JSON.stringify(variantConfigs[nodeId], null, 2);
            }}

            function closeConfig() {{
                document.getElementById('config-panel').classList.remove('open');
            }}

            window.addEventListener('load', function() {{
                // Le damos 150ms al navegador para que dibuje el layout completo antes de trazar las líneas
                setTimeout(function() {{
                    {chr(10).join(edges_js)}
                }}, 150);
            }});

            // Listener de scroll ajustado usando requestAnimationFrame para mayor rendimiento
            document.getElementById('pipeline-container').addEventListener('scroll', function() {{
                window.requestAnimationFrame(function() {{
                    lines.forEach(function(line) {{
                        line.position();
                    }});
                }});
            }});

            window.addEventListener('resize', function() {{
                lines.forEach(function(line) {{
                    line.position();
                }});
            }});
        </script>
    </body>
    </html>
    """

    os.makedirs(DST_HTML_DIR, exist_ok=True)
    output_path = os.path.join(DST_HTML_DIR, OUTPUT_FILENAME)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_template)
    print(f"Dashboard generado: {output_path}")

if __name__ == "__main__":
    build_html_dashboard()