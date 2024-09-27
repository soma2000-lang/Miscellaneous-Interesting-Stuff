import os
import ctypes
import threading
import logging
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from tree_sitter import Language, Parser

class TreeSitterWrapper:
    def __init__(self, language_name, grammar_path, cache_size=128):
        self.language_name = language_name
        self.grammar_path = grammar_path
        self.language = None
        self.parser = None
        self.setup()
        self.parse = lru_cache(maxsize=cache_size)(self._parse)
        self.logger = logging.getLogger(__name__)

    def setup(self):
        try:
            library_path = f"build/{self.language_name}.so"
            if not os.path.exists(library_path):
                Language.build_library(
                    library_path,
                    [self.grammar_path]
                )
            self.language = Language(library_path, self.language_name)
            self.parser = Parser()
            self.parser.set_language(self.language)
        except Exception as e:
            self.logger.error(f"Failed to set up Tree-sitter: {str(e)}")
            raise

    def _parse(self, code):
        try:
            return self.parser.parse(bytes(code, "utf8"))
        except Exception as e:
            self.logger.error(f"Parsing failed: {str(e)}")
            raise

    @lru_cache(maxsize=128)
    def query(self, query_string):
        try:
            return self.language.query(query_string)
        except Exception as e:
            self.logger.error(f"Query creation failed: {str(e)}")
            raise

    def execute_query(self, query, tree):
        try:
            return query.captures(tree.root_node)
        except Exception as e:
            self.logger.error(f"Query execution failed: {str(e)}")
            raise

    def print_tree(self, tree):
        def traverse(node, level=0):
            print("  " * level + f"{node.type}: {node.text.decode('utf8')}")
            for child in node.children:
                traverse(child, level + 1)
        traverse(tree.root_node)

    def parse_files(self, file_paths):
        results = {}
        with ThreadPoolExecutor() as executor:
            future_to_path = {executor.submit(self.parse_file, path): path for path in file_paths}
            for future in future_to_path:
                path = future_to_path[future]
                try:
                    results[path] = future.result()
                except Exception as e:
                    self.logger.error(f"Error parsing file {path}: {str(e)}")
                    results[path] = None
        return results

    def parse_file(self, file_path):
        try:
            with open(file_path, 'r') as file:
                content = file.read()
            return self.parse(content)
        except Exception as e:
            self.logger.error(f"Error reading or parsing file {file_path}: {str(e)}")
            raise

class CodeAnalyzer:
    def __init__(self, tree_sitter_wrapper):
        self.ts = tree_sitter_wrapper

    def find_functions(self, tree):
        query = self.ts.query('(function_definition name: (identifier) @function_name)')
        return [capture[0].text.decode('utf8') for capture in self.ts.execute_query(query, tree)]

    def find_variables(self, tree):
        query = self.ts.query('(variable_declarator name: (identifier) @variable_name)')
        return [capture[0].text.decode('utf8') for capture in self.ts.execute_query(query, tree)]

    def analyze_code_complexity(self, tree):
        # This is a simple example. In practice, you'd want a more sophisticated complexity analysis.
        query = self.ts.query('(if_statement) @if (for_statement) @for (while_statement) @while')
        results = self.ts.execute_query(query, tree)
        complexity = len(results)
        return complexity

def configure_logging():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        filename='tree_sitter_wrapper.log')

if __name__ == "__main__":
    configure_logging()

    # Assuming we have a Python grammar defined in 'grammars/python.js'
    ts = TreeSitterWrapper("python", "grammars/python.js")
    analyzer = CodeAnalyzer(ts)

    # Example Python code
    python_code = '''
def greet(name):
    print(f"Hello, {name}!")

def calculate_sum(a, b):
    result = a + b
    return result

for i in range(5):
    greet(f"User {i}")
    '''

    # Parse the code
    tree = ts.parse(python_code)

    # Analyze the code
    functions = analyzer.find_functions(tree)
    variables = analyzer.find_variables(tree)
    complexity = analyzer.analyze_code_complexity(tree)

    print("Functions:", functions)
    print("Variables:", variables)
    print("Complexity score:", complexity)

    # Example of parsing multiple files
    file_paths = ['file1.py', 'file2.py', 'file3.py']
    parsed_files = ts.parse_files(file_paths)
    for path, tree in parsed_files.items():
        if tree:
            print(f"\nAnalysis for {path}:")
            print("Functions:", analyzer.find_functions(tree))
            print("Complexity score:", analyzer.analyze_code_complexity(tree))
