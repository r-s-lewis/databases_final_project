from flask import Flask, render_template, request, jsonify
from db import run_explain_analyze, run_query_rows
import json
from graphviz import Digraph
import subprocess

app = Flask(__name__)

# You may need to adjust the paths based on your environment
LLAMA_BIN_PATH = "llama-b5273-bin-ubuntu-x64/bin"
MODEL_PATH = "final_project/sqlcoder-7b-q5_k_m.gguf"

def summarize_plan(plan_json):
    try:
        main = plan_json[0]['Plan']
        return {
            "Node Type": main.get("Node Type", "Unknown"),
            "Relation": main.get("Relation Name", "Unknown"),
            "Index Used": main.get("Index Name", "None"),
            "Actual Total Time (ms)": main.get("Actual Total Time", 0.0)
        }
    except Exception as e:
        return {"Error": f"Could not summarize plan: {e}"}

def build_plan_tree(plan_json):
    graph = Digraph(format='svg')
    graph.attr(bgcolor='transparent')
    graph.attr('node', style='filled', fillcolor='#222222', color='#0af', 
               fontcolor='#eeeeee', fontname='sans-serif')
    graph.attr('edge', color='#0af', fontcolor='#eeeeee')
    node_id = 0

    def add_node(plan, parent_id=None):
        nonlocal node_id
        current_id = f"node{node_id}"
        node_id += 1

        label = f"{plan['Node Type']}\n{plan.get('Relation Name', '')}\n{plan.get('Index Name', '')}".strip()
        graph.node(current_id, label=label)

        if parent_id:
            graph.edge(parent_id, current_id)

        for subplan in plan.get('Plans', []):
            add_node(subplan, current_id)

    add_node(plan_json[0]['Plan'])
    return graph.pipe().decode('utf-8')

def extract_timing_data(plan_json):
    timing_data = {}
    
    def traverse_plan(node):
        node_type = node.get('Node Type', 'Unknown')
        actual_time = node.get('Actual Total Time', 0)
        
        if node_type in timing_data:
            timing_data[node_type] = max(timing_data[node_type], actual_time)
        else:
            timing_data[node_type] = actual_time
            
        for subplan in node.get('Plans', []):
            traverse_plan(subplan)
    
    if plan_json and len(plan_json) > 0:
        traverse_plan(plan_json[0]['Plan'])
    
    return timing_data

@app.route("/stream_optimize", methods=["POST"])
def stream_optimize():
    query = request.form.get("query1", "")
    prompt = f"""### Task
Rewrite the following SQL query to improve performance. Prefer JOINs over subqueries, avoid SELECT *, and ensure the output is unchanged.

### Query
{query}

### Optimized SQL"""

    process = subprocess.Popen(
        ["./llama-cli", "-m", MODEL_PATH, "-p", prompt],
        cwd=LLAMA_BIN_PATH,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    full_output = []
    for line in process.stdout:
        full_output.append(line)

    process.wait()
    output_text = "".join(full_output)

    # Extract between "### Optimized SQL" and "[end of text]"
    optimized_sql = ""
    if "### Optimized SQL" in output_text:
        start = output_text.split("### Optimized SQL", 1)[1]
        end = start.split("[end of text]", 1)[0] if "[end of text]" in start else start
        optimized_sql = end.strip().replace("query", "", 1).strip()

    return jsonify({"optimized_sql": optimized_sql})

@app.route("/", methods=["GET", "POST"])
def index():
    result1 = result2 = summary1 = summary2 = diagram1 = diagram2 = ""
    query1 = query2 = ""
    query1_rows = query2_rows = []
    output_match = None
    timing_data1 = timing_data2 = {}

    if request.method == "POST" and "compare" in request.form:
        query1 = request.form.get("query1", "")
        query2 = request.form.get("query2", "")

        try:
            query1_rows = run_query_rows(query1)
            query2_rows = run_query_rows(query2)

            def normalize(rows):
                return sorted([tuple(sorted(row.items())) for row in rows])


            output_match = normalize(query1_rows) == normalize(query2_rows)
        except Exception as e:
            output_match = f"Error checking query outputs: {e}"

        try:
            plan1 = run_explain_analyze(query1)
            result1 = json.dumps(plan1, indent=2)
            summary1 = summarize_plan(plan1)
            diagram1 = build_plan_tree(plan1)
            timing_data1 = extract_timing_data(plan1)
        except Exception as e:
            result1 = json.dumps({"error": str(e)}, indent=2)
            summary1 = {"Error": str(e)}
            timing_data1 = {}

        try:
            plan2 = run_explain_analyze(query2)
            result2 = json.dumps(plan2, indent=2)
            summary2 = summarize_plan(plan2)
            diagram2 = build_plan_tree(plan2)
            timing_data2 = extract_timing_data(plan2)
        except Exception as e:
            result2 = json.dumps({"error": str(e)}, indent=2)
            summary2 = {"Error": str(e)}
            timing_data2 = {}
            
    return render_template("index.html",
                           query1=query1,
                           query2=query2,
                           result1=result1,
                           result2=result2,
                           summary1=summary1,
                           summary2=summary2,
                           diagram1=diagram1,
                           diagram2=diagram2,
                           query1_rows=query1_rows,
                           query2_rows=query2_rows,
                           output_match=output_match,
                           timing_data1=timing_data1,
                           timing_data2=timing_data2)

if __name__ == "__main__":
    app.run(debug=True, threaded=True)
