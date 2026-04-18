import ast
import os
import re
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════════════════════
#  ENTERPRISE RULE DATABASES
# ═══════════════════════════════════════════════════════════════════════════════

# ── SCA: Known Malicious / Deprecated / Dangerous Packages ──────────────────
_SCA_BLACKLIST: dict[str, str] = {
    # Typosquatting / confirmed malicious
    "colourama":        "Typosquatting malware (legitimate: 'colorama')",
    "python-sqlite":    "Known malicious package — use stdlib 'sqlite3'",
    "request":          "Typosquatting (legitimate: 'requests')",
    "urllib2":          "Python 2 only — use 'urllib.request' in Python 3",
    "cgi":              "Deprecated & removed in Python 3.13 (PEP 594) — use 'html' + 'http.server'",
    "imghdr":           "Deprecated & removed in Python 3.13 (PEP 594) — use 'filetype' or 'python-magic'",
    "aifc":             "Deprecated & removed in Python 3.13 (PEP 594)",
    "chunk":            "Deprecated & removed in Python 3.13 (PEP 594)",
    "crypt":            "Deprecated & removed in Python 3.13 (PEP 594) — use 'bcrypt' or 'argon2-cffi'",
    "pipes":            "Deprecated & removed in Python 3.13 (PEP 594) — use 'subprocess'",
    "telnetlib":        "Deprecated & removed in Python 3.13 (PEP 594) — use 'paramiko'",
    "uu":               "Deprecated & removed in Python 3.13 (PEP 594)",
    "xdrlib":           "Deprecated & removed in Python 3.13 (PEP 594)",
    "distutils":        "Deprecated & removed in Python 3.12 (PEP 632) — use 'setuptools'",
    "imp":              "Deprecated since 3.4, removed in 3.12 — use 'importlib'",
    "optparse":         "Soft-deprecated — prefer 'argparse'",
    "pickle":           "Unsafe deserialization — arbitrary code execution risk (use only on trusted data)",
    "shelve":           "Backed by pickle — same deserialization risk",
    "marshal":          "Unsafe deserialization — use only on trusted data",
    "xmlrpc":           "XML-RPC is unauthenticated by default — high attack surface",
    "pycrypto":         "Abandoned, unpatched CVEs — replace with 'cryptography' or 'pynacl'",
    "pycryptodome":     "Acceptable but verify you use the 'Crypto' namespace fork, not legacy 'pycrypto'",
    "M2Crypto":         "Abandoned wrapper — use 'cryptography' library instead",
    "paramiko":         "Audit required — often misconfigured (host key checking disabled)",
    "yaml":             "Use 'yaml.safe_load()' NOT 'yaml.load()' — arbitrary code execution risk",
    "jsonpickle":       "Unsafe deserialization — arbitrary code execution risk",
}

# ── SAST: Insecure hashlib algorithms ────────────────────────────────────────
_WEAK_HASH_ALGOS: set[str] = {"md5", "sha1", "sha"}

# ── SAST: Insecure SSL / TLS patterns ────────────────────────────────────────
_INSECURE_SSL_ATTRS: set[str] = {
    "PROTOCOL_SSLv2", "PROTOCOL_SSLv3", "PROTOCOL_TLSv1",
    "PROTOCOL_TLSv1_1", "CERT_NONE",
}

# ── SAST: Weak / banned cipher identifiers ───────────────────────────────────
_WEAK_CIPHERS: set[str] = {
    "DES", "3DES", "RC4", "RC2", "IDEA", "NULL",
    "EXPORT", "MD5", "SHA1", "anon",
}

# ── Secret Scanning: Regex patterns ──────────────────────────────────────────
_SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("AWS Access Key",      re.compile(r"(?<![A-Z0-9])(AKIA|ASIA|AROA)[A-Z0-9]{16}(?![A-Z0-9])")),
    ("AWS Secret Key",      re.compile(r"(?i)aws.{0,20}secret.{0,20}['\"]([A-Za-z0-9/+=]{40})['\"]")),
    ("GitHub Token",        re.compile(r"ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82}")),
    ("Generic API Token",   re.compile(r"(?i)(api[_\-]?key|token|secret)['\"]?\s*[:=]\s*['\"]([A-Za-z0-9\-_]{20,})['\"]")),
    ("JWT",                 re.compile(r"eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_.+/]+")),
    ("Private Key Header",  re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("Slack Token",         re.compile(r"xox[baprs]-[A-Za-z0-9\-]+")),
    ("Stripe Key",          re.compile(r"(sk|pk)_(live|test)_[A-Za-z0-9]{24,}")),
    ("Google API Key",      re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("Hardcoded Password",  re.compile(r"(?i)(password|passwd|pwd)\s*=\s*['\"](?!.*\{)[^'\"]{6,}['\"]")),
]

# ── AI Policy: Python 2 ghost patterns / unsafe casts ────────────────────────
_PY2_BUILTINS:    set[str] = {"print", "execfile", "raw_input", "reduce", "reload", "unicode", "basestring", "long", "xrange"}
_UNSAFE_CONVERSIONS: dict[str, str] = {
    "eval":    "Arbitrary code execution — use ast.literal_eval() for safe parsing",
    "exec":    "Arbitrary code execution — refactor to avoid dynamic execution",
    "compile": "Dynamic code compilation — high risk of code injection",
}

# ── SAST: Hardcoded credential variable names ────────────────────────────────
_CREDENTIAL_VARNAMES: re.Pattern = re.compile(
    r"(?i)^(password|passwd|pwd|secret|api_?key|auth_?token|access_?token|private_?key|client_?secret)$"
)

def _lines(nodes) -> str:
    unique = sorted(set(nodes))
    return "γραμμ" + ("ή" if len(unique) == 1 else "ές") + " " + ", ".join(map(str, unique))


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN DETECTOR CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class SpaghettiDetector(ast.NodeVisitor):
    def __init__(self):
        self.issues     = []
        self.file_issues = []   # File-level issues (unused imports, SCA, secrets)

        # ── Global Module State ──
        self.imports    = set()       # (name, lineno)
        self.used_names = set()

        # ── NEW: Enterprise tracking lists ──
        self.secrets_found = []       # [(description, lineno)]
        self.sca_issues    = []       # [(package, reason, lineno)]

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

        # ── SonarQube-style per-function ──
        self.func_stored_names  = set()
        self.func_loaded_names  = set()
        self.unreachable_lines  = []
        self.security_hotspots  = []    # SAST findings per function
        self.missing_type_hints = []
        self.ai_policy_lines    = []    # AI Coding Policy violations per function

    # ═══════════════════════════════════════════════════════════════════════
    #  MODULE & IMPORTS
    # ═══════════════════════════════════════════════════════════════════════

    def visit_Module(self, node):
        self.generic_visit(node)

        # Unused Imports
        unused = [name for name, line in self.imports if name not in self.used_names]
        if unused:
            self.file_issues.append(
                f"Unused Imports: Τα modules/classes {unused} έγιναν import αλλά δεν χρησιμοποιήθηκαν ποτέ."
            )
        # Flush SCA issues collected during import visits
        for pkg, reason, lineno in self.sca_issues:
            self.file_issues.append(
                f"⛔ SCA [γραμμή {lineno}]: Επικίνδυνο/deprecated package '{pkg}' → {reason}"
            )
        # Flush global secret findings
        for desc, lineno in self.secrets_found:
            self.file_issues.append(
                f"🔑 Secret Scanning [γραμμή {lineno}]: {desc}"
            )

    def _register_import(self, alias_name: str, real_name: str, lineno: int):
        """Shared helper: registers import and checks SCA blacklist."""
        self.imports.add((alias_name, lineno))
        # SCA check against blacklist (use the raw module name, e.g. 'pickle')
        root_pkg = real_name.split(".")[0]
        if root_pkg in _SCA_BLACKLIST:
            self.sca_issues.append((root_pkg, _SCA_BLACKLIST[root_pkg], lineno))

    def visit_Import(self, node):
        for alias in node.names:
            self._register_import(alias.asname or alias.name, alias.name, node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module or ""
        for alias in node.names:
            self._register_import(alias.asname or alias.name, module or alias.name, node.lineno)
        # Also check the top-level module itself
        root_pkg = module.split(".")[0]
        if root_pkg and root_pkg in _SCA_BLACKLIST and root_pkg not in {s[0] for s in self.sca_issues}:
            self.sca_issues.append((root_pkg, _SCA_BLACKLIST[root_pkg], node.lineno))
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
            if self.current_func:
                self.func_loaded_names.add(node.id)
                # ── AI Policy: Python 2 ghost builtins ──────────────────
                if node.id in _PY2_BUILTINS:
                    self.ai_policy_lines.append(
                        (node.id, node.lineno, f"Python 2 relic '{node.id}' — use the Python 3 equivalent")
                    )
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
        self.func_length = getattr(node, 'end_lineno', node.lineno) - node.lineno + 1

        self.bad_names          = []
        self.magic_numbers      = []
        self.silent_fail_lines  = []
        self.dup_blocks         = []
        self._seen_blocks       = {}
        self.func_stored_names  = set()
        self.func_loaded_names  = set()
        self.unreachable_lines  = []
        self.security_hotspots  = []
        self.missing_type_hints = []
        self.ai_policy_lines    = []

        # Type Hint Check
        if not node.returns and node.name != "__init__":
            self.missing_type_hints.append("return")
        for arg in getattr(node.args, 'args', []):
            if arg.arg not in ('self', 'cls') and not arg.annotation:
                self.missing_type_hints.append(arg.arg)

        self._check_unreachable(node.body)
        self.generic_visit(node)

        total_args = len(getattr(node.args, 'args', [])) + len(getattr(node.args, 'kwonlyargs', []))

        # Unused Variables
        unused_vars = [
            f"'{var}' (γραμμή {line})"
            for var, line in self.func_stored_names
            if var not in self.func_loaded_names and var != '_'
        ]

        # ── Build Issue List ──────────────────────────────────────────────
        func_issues = []
        func_start  = node.lineno
        func_end    = getattr(node, 'end_lineno', node.lineno)

        if self.func_length > 30:
            func_issues.append(
                f"God Function [γραμμές {func_start}–{func_end}]: Τεράστια συνάρτηση ({self.func_length} γραμμές)."
            )
        if len(self.if_else_lines) > 4:
            func_issues.append(
                f"Spaghetti Branching [{_lines(self.if_else_lines)}]: Έχει {len(self.if_else_lines)} μπλεγμένα if/else."
            )
        if self.max_nesting > 3:
            func_issues.append(
                f"Deep Nesting [γραμμή {self.max_nesting_line}]: Φτάνει σε βάθος {self.max_nesting} επιπέδων nesting!"
            )
        mutating = {v: ls for v, ls in self.var_assign_lines.items() if len(ls) > 3}
        if mutating:
            parts = [f"'{v}' ({_lines(ls)})" for v, ls in mutating.items()]
            func_issues.append(f"State Mutation: Οι μεταβλητές {', '.join(parts)} αλλάζουν τιμή πάνω από 3 φορές.")

        if len(self.jump_lines) > 4:
            func_issues.append(
                f"Unpredictable Flow [{_lines(self.jump_lines)}]: Έχει {len(self.jump_lines)} απότομα jumps."
            )
        if self.bad_names:
            parts = [f"'{n}' (γραμμή {ln})" for n, ln in self.bad_names]
            func_issues.append(f"Bad Naming: Ύποπτα ονόματα μεταβλητών → {', '.join(parts)}.")

        if total_args > 5:
            func_issues.append(
                f"Tight Coupling [γραμμή {func_start}]: Δέχεται {total_args} ορίσματα (>5)."
            )
        if self.magic_numbers:
            parts = [f"{v} (γραμμή {ln})" for v, ln in self.magic_numbers]
            func_issues.append(f"Magic Numbers: Hardcoded αριθμοί → {', '.join(parts)}.")

        if self.silent_fail_lines:
            func_issues.append(
                f"Silent Failure [{_lines(self.silent_fail_lines)}]: 'except Exception: pass' – errors καταπίνονται σιωπηλά!"
            )
        if self.dup_blocks:
            pairs = [f"γραμμές {a}↔{b}" for a, b in self.dup_blocks]
            func_issues.append(f"DRY Violation: Πανομοιότυπα blocks → {', '.join(pairs)}. Πιθανό copy-paste.")

        # ── SonarQube / Maintainability ───────────────────────────────────
        if self.missing_type_hints:
            func_issues.append(
                f"Maintainability: Λείπουν Type Hints στα ορίσματα/return: {', '.join(self.missing_type_hints)}"
            )
        if unused_vars:
            func_issues.append(
                f"Reliability (Unused Vars): Μεταβλητές που δεν διαβάστηκαν ποτέ → {', '.join(unused_vars)}"
            )
        if self.unreachable_lines:
            func_issues.append(
                f"Reliability (Dead Code): Unreachable κώδικας στις γραμμές: {', '.join(map(str, self.unreachable_lines))}."
            )

        # ── SAST Security Hotspots ────────────────────────────────────────
        if self.security_hotspots:
            parts = [f"{vuln} (γραμμή {ln})" for vuln, ln in self.security_hotspots]
            func_issues.append(
                f"🔐 SAST Security Hotspot: Επικίνδυνος κώδικας → {', '.join(parts)}"
            )

        # ── AI Coding Policy ──────────────────────────────────────────────
        if self.ai_policy_lines:
            parts = [f"'{name}' (γραμμή {ln}): {msg}" for name, ln, msg in self.ai_policy_lines]
            func_issues.append(
                f"🤖 AI Policy Violation: {'; '.join(parts)}"
            )

        if func_issues:
            self.issues.append((self.current_func, self.current_func_line, func_issues))

        self.current_func = None

    visit_AsyncFunctionDef = visit_FunctionDef

    # ═══════════════════════════════════════════════════════════════════════
    #  ASSIGNMENT — Secret Scanning + Hardcoded Credentials
    # ═══════════════════════════════════════════════════════════════════════

    def visit_Assign(self, node):
        _ALLOWED_SHORT = {"i", "j", "k", "x", "y", "_"}

        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue

            name = target.id
            self.var_assign_lines[name].append(node.lineno)

            # Bad naming
            if len(name) < 3 and name not in _ALLOWED_SHORT:
                self.bad_names.append((name, node.lineno))

            # ── Secret: hardcoded credential variable name with string RHS ──
            if _CREDENTIAL_VARNAMES.match(name) and isinstance(node.value, ast.Constant):
                val = str(node.value.value)
                # Ignore empty strings, placeholders and env-var-like values
                if len(val) >= 6 and not val.startswith("${") and val.lower() not in {
                    "none", "null", "undefined", "changeme", "placeholder", "your_token_here"
                }:
                    self._record_secret(
                        f"Hardcoded credential in variable '{name}' = '{val[:6]}…'",
                        node.lineno,
                    )

        # ── Secret: scan any string constant on RHS ─────────────────────────
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            self._scan_string_for_secrets(node.value.value, node.lineno)

        self.generic_visit(node)

    # ═══════════════════════════════════════════════════════════════════════
    #  CONSTANTS — Magic Numbers + Secret Scanning in free strings
    # ═══════════════════════════════════════════════════════════════════════

    def visit_Constant(self, node):
        # Magic numbers (function scope only)
        if self.current_func is not None:
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                if node.value not in {0, 1, -1}:
                    self.magic_numbers.append((node.value, getattr(node, 'lineno', 0)))

        # Secret scanning in any string literal (not already caught by visit_Assign)
        if isinstance(node.value, str):
            self._scan_string_for_secrets(node.value, getattr(node, 'lineno', 0))

        self.generic_visit(node)

    def _scan_string_for_secrets(self, value: str, lineno: int):
        """Run all secret regex patterns against a string value."""
        for label, pattern in _SECRET_PATTERNS:
            if pattern.search(value):
                self._record_secret(f"{label} detected in string literal", lineno)
                break   # one finding per literal is enough

    def _record_secret(self, description: str, lineno: int):
        """Deduplicate and register a secret finding."""
        entry = (description, lineno)
        if entry not in self.secrets_found:
            self.secrets_found.append(entry)

    # ═══════════════════════════════════════════════════════════════════════
    #  CALL — Advanced SAST
    # ═══════════════════════════════════════════════════════════════════════

    def visit_Call(self, node):
        lineno = getattr(node, 'lineno', 0)

        # ── eval / exec (existing) ───────────────────────────────────────
        if isinstance(node.func, ast.Name) and node.func.id in _UNSAFE_CONVERSIONS:
            func_id = node.func.id
            self.security_hotspots.append(
                (f"{func_id}() — {_UNSAFE_CONVERSIONS[func_id]}", lineno)
            )

        # ── shell=True ───────────────────────────────────────────────────
        for kw in node.keywords:
            if kw.arg == 'shell' and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                self.security_hotspots.append(
                    ("subprocess shell=True — OS command injection risk", lineno)
                )

        # ── Insecure hashlib (hashlib.md5, hashlib.sha1, etc.) ───────────
        # Pattern: hashlib.md5(...) or hashlib.new('md5', ...)
        if isinstance(node.func, ast.Attribute):
            attr  = node.func.attr.lower()
            owner = node.func.value

            if isinstance(owner, ast.Name) and owner.id == "hashlib":
                if attr in _WEAK_HASH_ALGOS:
                    self.security_hotspots.append(
                        (f"hashlib.{attr}() — weak/broken hash; use SHA-256+", lineno)
                    )
                # hashlib.new('md5', ...)
                if attr == "new" and node.args:
                    first = node.args[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        if first.value.lower() in _WEAK_HASH_ALGOS:
                            self.security_hotspots.append(
                                (f"hashlib.new('{first.value}') — weak/broken hash; use SHA-256+", lineno)
                            )

            # ── Insecure SSL context attributes ─────────────────────────
            # ssl.PROTOCOL_SSLv2, ssl.CERT_NONE, etc.
            if isinstance(owner, ast.Name) and owner.id == "ssl":
                if node.func.attr in _INSECURE_SSL_ATTRS:
                    self.security_hotspots.append(
                        (f"ssl.{node.func.attr} — insecure SSL/TLS configuration", lineno)
                    )

            # ── ssl.SSLContext(ssl.PROTOCOL_SSLv*) ───────────────────────
            if attr == "sslcontext" or (isinstance(owner, ast.Name) and attr in ("wrap_socket",)):
                for kw in node.keywords:
                    if kw.arg == "verify_mode" and isinstance(kw.value, ast.Attribute):
                        if kw.value.attr == "CERT_NONE":
                            self.security_hotspots.append(
                                ("SSLContext verify_mode=CERT_NONE — certificate verification disabled", lineno)
                            )

        # ── ssl.SSLContext instantiation with insecure protocol ──────────
        if isinstance(node.func, ast.Attribute) and node.func.attr == "SSLContext":
            if node.args:
                proto = node.args[0]
                if isinstance(proto, ast.Attribute) and proto.attr in _INSECURE_SSL_ATTRS:
                    self.security_hotspots.append(
                        (f"SSLContext({proto.attr}) — deprecated/insecure protocol", lineno)
                    )

        # ── Weak cipher strings in cryptography / pyOpenSSL calls ────────
        # e.g. context.set_ciphers("RC4:DES:NULL")
        if isinstance(node.func, ast.Attribute) and node.func.attr == "set_ciphers":
            if node.args and isinstance(node.args[0], ast.Constant):
                cipher_str: str = str(node.args[0].value).upper()
                for weak in _WEAK_CIPHERS:
                    if weak in cipher_str:
                        self.security_hotspots.append(
                            (f"set_ciphers('{node.args[0].value}') contains weak cipher '{weak}'", lineno)
                        )
                        break

        # ── AI Policy: unsafe builtins used as functions ─────────────────
        if isinstance(node.func, ast.Name) and node.func.id == "compile":
            if self.current_func:
                self.ai_policy_lines.append(
                    ("compile", lineno, _UNSAFE_CONVERSIONS["compile"])
                )

        # ── AI Policy: int(x) / float(x) on untrusted input (heuristic) ──
        # Flag type conversions where the argument is a subscript (e.g. int(data['x']))
        if isinstance(node.func, ast.Name) and node.func.id in ("int", "float", "complex"):
            if node.args and isinstance(node.args[0], ast.Subscript):
                if self.current_func:
                    self.ai_policy_lines.append((
                        node.func.id, lineno,
                        f"Unsafe type conversion {node.func.id}(dict_value) without try/except — "
                        f"will raise ValueError/TypeError on malformed input"
                    ))

        self.generic_visit(node)

    # ═══════════════════════════════════════════════════════════════════════
    #  ATTRIBUTE ACCESS — SSL constant usage outside calls
    # ═══════════════════════════════════════════════════════════════════════

    def visit_Attribute(self, node):
        """Catch ssl.CERT_NONE / ssl.PROTOCOL_SSLv* used as values (not only in calls)."""
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == "ssl"
            and node.attr in _INSECURE_SSL_ATTRS
            and self.current_func
        ):
            self.security_hotspots.append(
                (f"ssl.{node.attr} referenced — insecure SSL/TLS constant", getattr(node, 'lineno', 0))
            )
        self.generic_visit(node)

    # ═══════════════════════════════════════════════════════════════════════
    #  HELPERS & SUB-VISITORS  (unchanged from original)
    # ═══════════════════════════════════════════════════════════════════════

    def _check_unreachable(self, body):
        if not isinstance(body, list):
            return
        for i, stmt in enumerate(body):
            if isinstance(stmt, (ast.Return, ast.Break, ast.Continue, ast.Raise)):
                if i < len(body) - 1:
                    self.unreachable_lines.append(body[i + 1].lineno)
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

    def visit_ExceptHandler(self, node):
        is_bare = (
            node.type is None
            or (isinstance(node.type, ast.Name) and node.type.id == "Exception")
        )
        only_pass = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
        if is_bare and only_pass:
            self.silent_fail_lines.append(getattr(node, 'lineno', 0))
        self.generic_visit(node)


# ═══════════════════════════════════════════════════════════════════════════════
#  PROJECT RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_my_project(project_root: str) -> None:
    print(f"'CodeCheck Lite' (Enterprise Mode — v2.0)\n{'=' * 60}")

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

                        # File-level issues (unused imports, SCA, secrets)
                        for f_issue in detector.file_issues:
                            print(f"   ⚠️  [FILE LEVEL]: {f_issue}")

                        # Function-level issues
                        for func_name, func_line, issues in detector.issues:
                            total_spaghetti += 1
                            print(f"   ❌ Συνάρτηση '{func_name}()' (γραμμή {func_line}):")
                            for issue in issues:
                                print(f"      - {issue}")

                        print("-" * 60)

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
