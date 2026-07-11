import os
import csv
import ast
import subprocess

from dotenv import load_dotenv


load_dotenv()

# parameters to extract
target_variables = {'temperature', 'top_k', 'top_p', 'min_p', 'frequency_penalty', 'presence_penalty', 'repetition_penalty', 'max_tokens', 'model'}


def extract_variable_assignments(tree):
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in target_variables:
                    if isinstance(node.value, (ast.Constant, ast.Num)):
                        if (target.id == 'model' and node.value.value) or (target.id != 'model' and node.value.value is not None and isinstance(node.value.value, (int, float))):
                            results.append((project_name, os.path.abspath(file_path), target.lineno, target.id, node.value.value))
                elif isinstance(target, ast.Attribute) and target.attr in target_variables:
                    if isinstance(node.value, (ast.Constant, ast.Num)):
                        if (target.attr == 'model' and node.value.value) or (target.attr != 'model' and node.value.value is not None and isinstance(node.value.value, (int, float))):
                            results.append((project_name, os.path.abspath(file_path), target.lineno,target.attr, node.value.value))
                elif isinstance(node.value, ast.Dict):
                    for key_node, value_node in zip(node.value.keys, node.value.values):
                        if isinstance(key_node, ast.Constant) and key_node.value in target_variables:
                            if isinstance(value_node, (ast.Constant, ast.Num)):
                                if (key_node.value == 'model' and value_node.value) or (key_node.value != 'model' and value_node.value is not None and isinstance(value_node.value, (int, float))):
                                    results.append((project_name, os.path.abspath(file_path), target.lineno, key_node.value, value_node.value))
        elif isinstance(node, ast.AnnAssign):
            t = node.target
            param = None

            if isinstance(t, ast.Name) and t.id in target_variables:
                param = t.id
            elif isinstance(t, ast.Attribute) and t.attr in target_variables:
                param = t.attr

            if param is not None:
                if isinstance(node.value, (ast.Constant, ast.Num)):
                    val = node.value.value
                else:
                    continue

                if (param == 'model' and val) or (param != 'model' and val is not None and isinstance(val, (int, float))):
                    results.append((project_name, os.path.abspath(file_path), node.lineno, param, val))
    return results


def find_parameter_usage_in_function_calls(tree):
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            used_params = []
            for kw in node.keywords:
                if kw.arg in target_variables:
                    if isinstance(kw.value, (ast.Constant, ast.Num)):
                        used_params.append((kw.arg, kw.value.value))
            if used_params and not 'Field' in func_name:
                for param in used_params:
                    if (param[0] == 'model' and param[1]) or (param[0] != 'model' and param[1] is not None and isinstance(param[1], (int, float))):
                        results.append((project_name, os.path.abspath(file_path), node.lineno, param[0], param[1]))
    return results


def find_parameter_usage_in_function_definitions(tree):
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):

            args = node.args.args
            defaults = node.args.defaults

            if not defaults:
                continue

            aligned_args = args[-len(defaults):]

            for arg, default in zip(aligned_args, defaults):
                if arg.arg in target_variables:

                    if isinstance(default, (ast.Constant, ast.Num)):
                        val = default.value
                    else:
                        continue

                    if (arg.arg == 'model' and val) or (arg.arg != 'model' and val is not None and isinstance(val, (int, float))):
                        results.append((project_name, os.path.abspath(file_path), node.lineno, arg.arg, val))
    return results


def find_parameter_usage_in_class_defs(tree):
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            used_params = []
            for subnode in ast.walk(node):
                if isinstance(subnode, ast.Assign):
                    for target in subnode.targets:
                        if isinstance(target, ast.Name) and target.id in target_variables:
                            if isinstance(subnode.value, (ast.Constant, ast.Num)):
                                used_params.append((target.id, subnode.value.value))
                        elif isinstance(target, ast.Attribute) and target.attr in target_variables:
                            if isinstance(subnode.value, (ast.Constant, ast.Num)):
                                used_params.append((target.attr, subnode.value.value))
                elif isinstance(subnode, ast.AnnAssign):
                    t = subnode.target
                    param = None

                    if isinstance(t, ast.Name) and t.id in target_variables:
                        param = t.id
                    elif isinstance(t, ast.Attribute) and t.attr in target_variables:
                        param = t.attr

                    if param is not None and isinstance(subnode.value, (ast.Constant, ast.Num)):
                        used_params.append((param, subnode.value.value))
                elif isinstance(subnode, ast.Dict):
                    for key_node, value_node in zip(subnode.keys, subnode.values):
                        if isinstance(key_node, ast.Constant) and key_node.value in target_variables:
                            if isinstance(value_node, (ast.Constant, ast.Num)):
                                used_params.append((key_node.value, value_node.value))
            if used_params and not 'Field' in class_name:
                for param in used_params:
                    if (param[0] == 'model' and param[1]) or (param[0] != 'model' and param[1] is not None and isinstance(param[1], (int, float))):
                        results.append((project_name, os.path.abspath(file_path), node.lineno, param[0], param[1]))
    return results


def find_additional_parameter_patterns(tree):
    results = []

    for node in ast.walk(tree):

        # ---------------------------------------------------
        # (A) dataclasses: field(default=...)
        # ---------------------------------------------------
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.value, ast.Call):
                if isinstance(node.value.func, ast.Name) and node.value.func.id == "field":
                    for kw in node.value.keywords:
                        if kw.arg == "default":
                            if isinstance(node.target, ast.Name) and node.target.id in target_variables:
                                if isinstance(kw.value, (ast.Constant, ast.Num)):
                                    val = kw.value.value
                                    param = node.target.id
                                    if (param == 'model' and val) or (param != 'model' and val is not None and isinstance(val, (int, float))):
                                        results.append((project_name, os.path.abspath(file_path), node.lineno, param, val))
                            elif isinstance(node.target, ast.Attribute) and node.target.attr in target_variables:
                                if isinstance(kw.value, (ast.Constant, ast.Num)):
                                    val = kw.value.value
                                    param = node.target.attr
                                    if (param == 'model' and val) or (param != 'model' and val is not None and isinstance(val, (int, float))):
                                        results.append((project_name, os.path.abspath(file_path), node.lineno, param, val))

        # ---------------------------------------------------
        # (B) dict(model="gpt-4", top_p=0.8)
        # ---------------------------------------------------
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "dict":
                for kw in node.keywords:
                    if kw.arg in target_variables:
                        if isinstance(kw.value, (ast.Constant, ast.Num)):
                            val = kw.value.value
                            param = kw.arg
                            if (param == 'model' and val) or (param != 'model' and val is not None and isinstance(val, (int, float))):
                                results.append((project_name, os.path.abspath(file_path), node.lineno, param, val))

        # ---------------------------------------------------
        # (C) List of pairs: [("model", "gpt-4")]
        # ---------------------------------------------------
        if isinstance(node, (ast.List, ast.Tuple)):
            for elt in node.elts:
                if isinstance(elt, ast.Tuple) and len(elt.elts) == 2:
                    key_node, value_node = elt.elts
                    if isinstance(key_node, ast.Constant) and key_node.value in target_variables:
                        if isinstance(value_node, (ast.Constant, ast.Num)):
                            val = value_node.value
                            param = key_node.value
                            if (param == 'model' and val) or (param != 'model' and val is not None and isinstance(val, (int, float))):
                                results.append((project_name, os.path.abspath(file_path), node.lineno, param, val))

        # ---------------------------------------------------
        # (D) Destructuring: model, top_p = ("gpt-4", 0.8)
        # ---------------------------------------------------
        if isinstance(node, ast.Assign):
            if isinstance(node.targets[0], ast.Tuple) and isinstance(node.value, ast.Tuple):
                targets = node.targets[0].elts
                values = node.value.elts
                for t, v in zip(targets, values):
                    if isinstance(t, ast.Name) and t.id in target_variables:
                        if isinstance(v, (ast.Constant, ast.Num)):
                            val = v.value
                            param = t.id
                            if (param == 'model' and val) or (param != 'model' and val is not None and isinstance(val, (int, float))):
                                results.append((project_name, os.path.abspath(file_path), node.lineno, param, val))

        # ---------------------------------------------------
        # (E) config.get("model")
        # ---------------------------------------------------
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
                # node.func.value = objeto del cual se hace get()
                # node.args = argumentos del get()
                if node.args and isinstance(node.args[0], ast.Constant):
                    key = node.args[0].value
                    if key in target_variables:
                        # obtener default si existe, p.ej config.get("model", "gpt-4")
                        if len(node.args) > 1 and isinstance(node.args[1], (ast.Constant, ast.Num)):
                            val = node.args[1].value
                            param = key
                            if (param == 'model' and val) or (param != 'model' and val is not None and isinstance(val, (int, float))):
                                results.append((project_name, os.path.abspath(file_path), node.lineno, param, val))

    return results


def clone_repos(dataset_path, base_path):
    cloned_repos = 0
    with open(dataset_path, 'r') as a_file:
        reader = csv.reader(a_file, delimiter=';')
        next(reader)
        for row in reader:
            # clone repo 
            url = row[3]
            result = subprocess.run(['git', 'clone', url],
                                    cwd=base_path, capture_output=True)
            if result.returncode != 0:
                cloned_repos += 1
    return cloned_repos


project_dataset_path = os.getenv("PROJECT_DATASET_PATH")
source_directory = os.getenv("SOURCE_DIRECTORY")

print("cloning repositories ...")
clone_repos(project_dataset_path, source_directory)

print("extracting parameters ...")
all_results = []
for root, _, files in os.walk(source_directory):
    for file in files:
        if file.endswith(".py"):
            project_name = root.split('/')[6]
            file_path = os.path.join(root, file)
            if (not 'doc' in file_path.lower()) and (not 'test' in file_path.lower()) and (not 'readme' in file_path.lower()) and (not 'fixture' in file_path.lower()) and (not 'benchmark' in file_path.lower()) and (not 'example' in file_path.lower()) and (not 'deprecated' in file_path.lower()) and (not 'not_working' in file_path.lower()) and (not 'demo' in file_path.lower()) and (not 'beta' in file_path.lower()) and (not 'migrations' in file_path.lower()) and (not 'samples' in file_path.lower()) and (not 'lock' in file_path.lower()) and (not 'evaluation' in file_path.lower()) and (not 'result' in file_path.lower()) and (not 'schema' in file_path.lower()) and (not 'experimental' in file_path.lower()) and (not 'tutorial' in file_path.lower()) and (not 'dataset' in file_path.lower()) and (not 'db' in file_path.lower()) and (not 'database' in file_path.lower()):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        source = f.read()
                    tree = ast.parse(source, filename=file_path)
                    all_results.extend(extract_variable_assignments(tree))
                    all_results.extend(find_parameter_usage_in_function_calls(tree))
                    all_results.extend(find_parameter_usage_in_function_definitions(tree))
                    all_results.extend(find_parameter_usage_in_class_defs(tree))
                    all_results.extend(find_additional_parameter_patterns(tree))
                except Exception as e:
                    print(f"Error procesando {file_path}: {e}")

# Save CSV file
output_csv = "projects_parameter_assignments.csv"
with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['project_name', 'path', 'lineno', 'parameter', 'value'])
    writer.writerows(all_results)

print(f"Extraction complete. Results saved in {output_csv}.")
