import pytest
from streamlit.testing.v1 import AppTest

class TestStreamlitDashboard:
    
    @pytest.fixture(scope="class")
    def app(self):
        at = AppTest.from_file("app.py", default_timeout=15)
        return at

    def test_ui_loads_without_exceptions(self, app):
        """Ανεβαίνει το UI χωρίς Red Screen;"""
        app.run()
        assert not app.exception, f"UI crashed! Error: {app.exception[0] if app.exception else ''}"

    def test_ui_simulate_user_interaction(self, app):
        """Προσομοίωση χρήστη: Πληκτρολόγηση και πάτημα κουμπιού 'Analyze Intent'."""
        app.run()
        
        # 1. Βρίσκουμε το sidebar text_input (είναι το πρώτο στο αρχείο σου) και γράφουμε κάτι
        # Στο app.py έχεις: st.sidebar.text_input("Command:")
        app.sidebar.text_input[0].input("I am testing the system").run()
        
        # 2. Βρίσκουμε το κουμπί "Analyze Intent" και το πατάμε
        # Είναι το πρώτο κουμπί στο sidebar!
        app.sidebar.button[0].click().run()
        
        # 3. Ελέγχουμε ότι δεν έσκασε το Streamlit μετά το πάτημα (π.χ. από λάθος JSON parse)
        assert not app.exception, "UI crashed after clicking 'Analyze Intent'!"