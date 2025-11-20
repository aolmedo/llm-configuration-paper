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
                # Variable simple
                if isinstance(target, ast.Name) and target.id in target_variables:
                    if isinstance(node.value, (ast.Constant, ast.Num)):                        
                        if node.value.value and (target.id == 'model' or (target.id != 'model' and isinstance(node.value.value, (int, float)))):
                            results.append((project_name, os.path.abspath(file_path), target.lineno, target.id, node.value.value))
                # Atributo como config.temperature
                elif isinstance(target, ast.Attribute) and target.attr in target_variables:
                    if isinstance(node.value, (ast.Constant, ast.Num)):
                        if node.value.value and (target.attr == 'model' or (target.attr != 'model' and isinstance(node.value.value, (int, float)))):
                            results.append((project_name, os.path.abspath(file_path), target.lineno,target.attr, node.value.value))
                # Diccionario con parámetros
                elif isinstance(node.value, ast.Dict):
                    for key_node, value_node in zip(node.value.keys, node.value.values):
                        if isinstance(key_node, ast.Constant) and key_node.value in target_variables:
                            if isinstance(value_node, (ast.Constant, ast.Num)):
                                if value_node.value and (key_node.value == 'model' or (key_node.value != 'model' and isinstance(value_node.value, (int, float)))):
                                    results.append((project_name, os.path.abspath(file_path), target.lineno, key_node.value, value_node.value))
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
                    if param[1] and (param[0] == 'model' or (param[0] != 'model' and isinstance(param[1], (int, float)))):
                        results.append((project_name, os.path.abspath(file_path), node.lineno, param[0], param[1]))
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
                elif isinstance(subnode, ast.Dict):
                    for key_node, value_node in zip(subnode.keys, subnode.values):
                        if isinstance(key_node, ast.Constant) and key_node.value in target_variables:
                            if isinstance(value_node, (ast.Constant, ast.Num)):
                                used_params.append((key_node.value, value_node.value))
            if used_params and not 'Field' in class_name:
                for param in used_params:
                    if param[1] and (param[0] == 'model' or (param[0] != 'model' and isinstance(param[1], (int, float)))):
                        results.append((project_name, os.path.abspath(file_path), node.lineno, param[0], param[1]))
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
                    all_results.extend(find_parameter_usage_in_class_defs(tree))
                except Exception as e:
                    print(f"Error procesando {file_path}: {e}")

# Save CSV file
output_csv = "projects_parameter_assignments.csv"
with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['project_name', 'path', 'lineno', 'parameter', 'value'])
    writer.writerows(all_results)

print(f"Extraction complete. Results saved in {output_csv}.")
