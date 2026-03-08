import ast
import os
from collections import defaultdict

def _lines(nodes) -> str:
    unique = sorted(set(nodes))
    return "γραμμ" + ("ή" if len(unique) == 1 else "ές") + " " + ", ".join(map(str, unique))

class SpaghettiDetector(ast.NodeVisitor):
    def __init__(self):
        self.issues = []
        self.file_issues = [] # Για προβλήματα σε επίπεδο αρχείου (π.χ. unused imports)
        
        # ── Global Module State ──
        self.imports = set()      # (name, lineno)
        self.used_names = set()   # Ονόματα που διαβάστηκαν σε όλο το αρχείο

        # ── Per-function state ──
        self.current_func      = None
        self.current_func_line = 0

        self.nesting_depth     = 0
        self.max_nesting       = 0
        self.max_nesting_line  = 0
        self.if_else_lines     = []
        self.loop_count        = 0
        self.jump_lines        = []
        self.var_assign_lines  = defaultdict(list)
        self.func_length       = 0

        self.bad_names         = []
        self.magic_numbers     = []
        self.silent_fail_lines = []
        self.dup_blocks        = []
        self._seen_blocks      = {}

        # ── NEW SONARQUBE FEATURES ──
        self.func_stored_names = set()
        self.func_loaded_names = set()
        self.unreachable_lines = []
        self.security_hotspots = []
        self.missing_type_hints= []

    # ═══════════════════════════════════════════════════════════════════════
    #  MODULE & IMPORTS VISITOR
    # ═══════════════════════════════════════════════════════════════════════
    def visit_Module(self, node):
        self.generic_visit(node)
        # Όταν τελειώσει το αρχείο, βρίσκουμε τα Unused Imports
        unused_imports = [name for name, line in self.imports if name not in self.used_names]
        if unused_imports:
            self.file_issues.append(f"Unused Imports: Τα modules/classes {unused_imports} έγιναν import αλλά δεν χρησιμοποιήθηκαν ποτέ.")

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add((alias.asname or alias.name, node.lineno))
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        for alias in node.names:
            self.imports.add((alias.asname or alias.name, node.lineno))
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
            if self.current_func:
                self.func_loaded_names.add(node.id)
        elif isinstance(node.ctx, ast.Store):
            if self.current_func:
                self.func_stored_names.add((node.id, node.lineno))
        self.generic_visit(node)

    # ═══════════════════════════════════════════════════════════════════════
    #  FUNCTION-LEVEL VISITOR
    # ═══════════════════════════════════════════════════════════════════════
    def visit_FunctionDef(self, node):
        self.current_func      = node.name
        self.current_func_line = node.lineno
        self.nesting_depth     = 0
        self.max_nesting       = 0
        self.max_nesting_line  = 0
        self.if_else_lines     = []
        self.loop_count        = 0
        self.jump_lines        = []
        self.var_assign_lines.clear()
        self.func_length       = getattr(node, 'end_lineno', node.lineno) - node.lineno + 1
        
        self.bad_names         = []
        self.magic_numbers     = []
        self.silent_fail_lines = []
        self.dup_blocks        = []
        self._seen_blocks      = {}

        self.func_stored_names = set()
        self.func_loaded_names = set()
        self.unreachable_lines = []
        self.security_hotspots = []
        self.missing_type_hints= []

        # -- Type Hint Check --
        if not node.returns and node.name != "__init__":
            self.missing_type_hints.append("return")
        for arg in getattr(node.args, 'args', []):
            if arg.arg not in ('self', 'cls') and not arg.annotation:
                self.missing_type_hints.append(arg.arg)

        # -- Check Unreachable --
        self._check_unreachable(node.body)

        self.generic_visit(node)

        total_args = len(getattr(node.args, 'args', [])) + len(getattr(node.args, 'kwonlyargs', []))

        # -- Unused Variables Check --
        unused_vars = []
        for var, line in self.func_stored_names:
            if var not in self.func_loaded_names and var != '_':
                unused_vars.append(f"'{var}' (γραμμή {line})")

        # ── Build Issue List ──
        func_issues = []
        func_start  = node.lineno
        func_end    = getattr(node, 'end_lineno', node.lineno)

        if self.func_length > 30:
            func_issues.append(f"God Function [γραμμές {func_start}–{func_end}]: Τεράστια συνάρτηση ({self.func_length} γραμμές).")

        if len(self.if_else_lines) > 4:
            func_issues.append(f"Spaghetti Branching [{_lines(self.if_else_lines)}]: Έχει {len(self.if_else_lines)} μπλεγμένα if/else.")

        if self.max_nesting > 3:
            func_issues.append(f"Deep Nesting [γραμμή {self.max_nesting_line}]: Φτάνει σε βάθος {self.max_nesting} επιπέδων nesting!")

        mutating = {v: ls for v, ls in self.var_assign_lines.items() if len(ls) > 3}
        if mutating:
            parts = [f"'{v}' ({_lines(ls)})" for v, ls in mutating.items()]
            func_issues.append(f"State Mutation: Οι μεταβλητές {', '.join(parts)} αλλάζουν τιμή πάνω από 3 φορές.")

        if len(self.jump_lines) > 4:
            func_issues.append(f"Unpredictable Flow [{_lines(self.jump_lines)}]: Έχει {len(self.jump_lines)} απότομα jumps.")

        if self.bad_names:
            parts = [f"'{n}' (γραμμή {ln})" for n, ln in self.bad_names]
            func_issues.append(f"Bad Naming: Ύποπτα ονόματα μεταβλητών → {', '.join(parts)}.")

        if total_args > 5:
            func_issues.append(f"Tight Coupling [γραμμή {func_start}]: Δέχεται {total_args} ορίσματα (>5).")

        if self.magic_numbers:
            parts = [f"{v} (γραμμή {ln})" for v, ln in self.magic_numbers]
            func_issues.append(f"Magic Numbers: Hardcoded αριθμοί → {', '.join(parts)}.")

        if self.silent_fail_lines:
            func_issues.append(f"Silent Failure [{_lines(self.silent_fail_lines)}]: 'except Exception: pass' – errors καταπίνονται σιωπηλά!")

        if self.dup_blocks:
            pairs = [f"γραμμές {a}↔{b}" for a, b in self.dup_blocks]
            func_issues.append(f"DRY Violation: Πανομοιότυπα blocks → {', '.join(pairs)}. Πιθανό copy-paste.")

        # -- SonarQube Issues --
        if self.missing_type_hints:
            func_issues.append(f"Maintainability: Λείπουν Type Hints στα ορίσματα/return: {', '.join(self.missing_type_hints)}")
            
        if unused_vars:
            func_issues.append(f"Reliability (Unused Vars): Εντοπίστηκαν μεταβλητές που πήραν τιμή αλλά δεν διαβάστηκαν ποτέ → {', '.join(unused_vars)}")
            
        if self.unreachable_lines:
            func_issues.append(f"Reliability (Dead Code): Βρέθηκε Unreachable κώδικας στις γραμμές: {', '.join(map(str, self.unreachable_lines))} (μετά από return/break/continue/raise).")
            
        if self.security_hotspots:
            parts = [f"{vuln} (γραμμή {ln})" for vuln, ln in self.security_hotspots]
            func_issues.append(f"Security Hotspot: Προσοχή, εντοπίστηκε επικίνδυνος κώδικας → {', '.join(parts)}")

        if func_issues:
            self.issues.append((self.current_func, self.current_func_line, func_issues))

        self.current_func = None
        
    visit_AsyncFunctionDef = visit_FunctionDef

    # ═══════════════════════════════════════════════════════════════════════
    #  HELPERS & SUB-VISITORS
    # ═══════════════════════════════════════════════════════════════════════
    def _check_unreachable(self, body):
        """Ελέγχει αν υπάρχει κώδικας κάτω από return, break, continue, raise στο ίδιο block"""
        if not isinstance(body, list): return
        for i, stmt in enumerate(body):
            if isinstance(stmt, (ast.Return, ast.Break, ast.Continue, ast.Raise)):
                if i < len(body) - 1:
                    self.unreachable_lines.append(body[i+1].lineno)
                break

    def _track_nesting(self, node):
        self.nesting_depth += 1
        if self.nesting_depth > self.max_nesting:
            self.max_nesting      = self.nesting_depth
            self.max_nesting_line = getattr(node, 'lineno', 0)
        self.generic_visit(node)
        self.nesting_depth -= 1

    def _check_dry(self, stmts):
        for stmt in stmts:
            for child in ast.walk(stmt):
                if not isinstance(child, (ast.If, ast.For, ast.While)):
                    continue
                body = getattr(child, "body", [])
                if len(body) < 2:
                    continue
                dump = ast.dump(ast.Module(body=body, type_ignores=[]))
                if dump in self._seen_blocks:
                    self.dup_blocks.append((self._seen_blocks[dump], getattr(child, 'lineno', 0)))
                else:
                    self._seen_blocks[dump] = getattr(child, 'lineno', 0)

    def visit_If(self, node):
        self.if_else_lines.append(node.lineno)
        self._check_unreachable(node.body)
        self._check_unreachable(node.orelse)
        self._check_dry(node.body)
        if node.orelse:
            self._check_dry(node.orelse)
        self._track_nesting(node)

    def visit_For(self, node):
        self.loop_count += 1
        self._check_unreachable(node.body)
        self._check_dry(node.body)
        self._track_nesting(node)

    def visit_While(self, node):
        self.loop_count += 1
        self._check_unreachable(node.body)
        self._check_dry(node.body)
        self._track_nesting(node)

    def visit_Try(self, node):
        self._check_unreachable(node.body)
        self._check_dry(node.body)
        self.generic_visit(node)

    def visit_Assign(self, node):
        _ALLOWED_SHORT = {"i", "j", "k", "x", "y", "_"}
        for target in node.targets:
            if isinstance(target, ast.Name):
                name = target.id
                self.var_assign_lines[name].append(node.lineno)
                if len(name) < 3 and name not in _ALLOWED_SHORT:
                    self.bad_names.append((name, node.lineno))
        self.generic_visit(node)

    def visit_Return(self, node):
        self.jump_lines.append(node.lineno)
        self.generic_visit(node)

    def visit_Break(self, node):
        self.jump_lines.append(node.lineno)
        self.generic_visit(node)

    def visit_Continue(self, node):
        self.jump_lines.append(node.lineno)
        self.generic_visit(node)

    def visit_Global(self, node):
        self.jump_lines.extend([node.lineno, node.lineno])
        self.generic_visit(node)

    def visit_Constant(self, node):
        if self.current_func is None:
            return 
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            if node.value not in {0, 1, -1}:
                self.magic_numbers.append((node.value, getattr(node, 'lineno', 0)))
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        is_bare = (
            node.type is None
            or (isinstance(node.type, ast.Name) and node.type.id == "Exception")
        )
        only_pass = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
        if is_bare and only_pass:
            self.silent_fail_lines.append(getattr(node, 'lineno', 0))
        self.generic_visit(node)

    def visit_Call(self, node):
        # Security Hotspot: eval, exec
        if isinstance(node.func, ast.Name) and node.func.id in ('eval', 'exec'):
            self.security_hotspots.append((node.func.id, getattr(node, 'lineno', 0)))
        # Security Hotspot: shell=True
        for kw in node.keywords:
            if kw.arg == 'shell' and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                self.security_hotspots.append(('shell=True', getattr(node, 'lineno', 0)))
        self.generic_visit(node)


def analyze_my_project(project_root: str) -> None:
    print(f"'CodeCheck Lite' (Enterprise Mode)\n{'=' * 50}")

    allowed_dirs    = {"python_backend", "python_ai_agent", "testing"}
    files_checked   = 0
    total_spaghetti = 0

    for root, dirs, files in os.walk(project_root):
        current_folder = os.path.basename(root)
        if (
            current_folder != os.path.basename(project_root)
            and current_folder not in allowed_dirs
        ):
            dirs[:] = []
            continue

        for file in files:
            if file.endswith(".py") and file not in {"ast_visitors.py", "run_analyzer.py"}:
                file_path = os.path.join(root, file)
                files_checked += 1

                with open(file_path, "r", encoding="utf-8") as fh:
                    source_code = fh.read()

                try:
                    tree     = ast.parse(source_code)
                    detector = SpaghettiDetector()
                    detector.visit(tree)

                    if detector.issues or detector.file_issues:
                        print(f"\n🚨 Αρχείο: {file}")
                        
                        # Print File level issues (Unused imports)
                        for f_issue in detector.file_issues:
                            print(f"   ⚠️  [FILE LEVEL]: {f_issue}")

                        # Print Function level issues
                        for func_name, func_line, issues in detector.issues:
                            total_spaghetti += 1
                            print(f"   ❌ Συνάρτηση '{func_name}()' (γραμμή {func_line}):")
                            for issue in issues:
                                print(f"      - {issue}")
                        print("-" * 50)
                except SyntaxError as exc:
                    print(f"   ⚠️  Syntax error στο {file}: {exc}")
                except Exception:
                    pass

    print(f"\n📊 SUMMARY: Ελέγχθηκαν {files_checked} αρχεία.")
    if total_spaghetti == 0:
        print("✅ ΑΠΟΤΕΛΕΣΜΑ: Πεντακάθαρος κώδικας.")
    else:
        print(f"⚠️  ΑΠΟΤΕΛΕΣΜΑ: Βρέθηκαν {total_spaghetti} συναρτήσεις με παραβιάσεις.")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    thesis_dir = os.path.dirname(script_dir)
    analyze_my_project(thesis_dir)