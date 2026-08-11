// App.jsx — Composant principal de l'application
// Objectif : vérifier que le frontend peut communiquer avec le backend FastAPI

import { useState, useEffect } from "react"; 
// useState : permet de stocker et mettre à jour une donnée qui affecte l'affichage
// useEffect : permet d'exécuter du code au chargement du composant (ici : appeler l'API)

function App() {
  // État qui va stocker la réponse du backend (au départ : rien)
  const [backendStatus, setBackendStatus] = useState(null);
  const [error, setError] = useState(null);

  // useEffect avec un tableau de dépendances vide [] = s'exécute UNE SEULE FOIS,
  // juste après le premier affichage du composant (équivalent d'un "au chargement de la page")
  useEffect(() => {
    fetch("http://127.0.0.1:8000/health")
      .then((response) => response.json()) // Convertit la réponse en objet JS
      .then((data) => setBackendStatus(data.status)) // Stocke le statut reçu
      .catch((err) => setError("Impossible de contacter le backend : " + err.message));
  }, []);

  return (
    <div style={{ padding: "40px", fontFamily: "sans-serif" }}>
      <h1>Leoni Maintenance Ticketing System</h1>

      {/* Affichage conditionnel selon l'état de la connexion */}
      {error && <p style={{ color: "red" }}>{error}</p>}
      {!error && backendStatus === null && <p>Connexion au backend en cours...</p>}
      {!error && backendStatus && (
        <p style={{ color: "green" }}>
          ✅ Backend connecté — statut : {backendStatus}
        </p>
      )}
    </div>
  );
}

export default App;