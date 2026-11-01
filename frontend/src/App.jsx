// App.jsx — Interface principale de gestion des tickets de maintenance
// Design : "cartouche de plan technique" — inspiré des fiches d'ingénierie
// utilisées dans l'industrie du câblage automobile.

import { useState, useEffect } from "react";

// URL de l'API, injectée par Vite AU MOMENT DU BUILD (pas au démarrage du conteneur) :
// - npm run dev        → frontend/.env.development (http://127.0.0.1:8000) ;
// - image Docker Azure → valeur par défaut de l'ARG du Dockerfile (http://127.0.0.1:8000) ;
// - image Kubernetes   → VITE_API_URL="" → URLs relatives (/api/...) servies via l'Ingress.
// "??" ne remplace que si la variable est absente : une chaîne vide reste vide (= relatif).
const API_URL = import.meta.env.VITE_API_URL ?? "";

const STATUS_STYLES = {
  Open: "border-l-4 border-red-signal bg-red-50 text-red-signal",
  InProgress: "border-l-4 border-amber-signal bg-amber-50 text-amber-signal",
  Resolved: "border-l-4 border-blueprint-700 bg-blue-50 text-blueprint-700",
  Closed: "border-l-4 border-green-signal bg-emerald-50 text-green-signal",
};

const PRIORITY_DOT = {
  Low: "bg-steel-400",
  Medium: "bg-amber-signal",
  High: "bg-red-signal",
};

const STATUS_OPTIONS = ["Open", "InProgress", "Resolved", "Closed"];

const formatWorkOrder = (id) => `WO-${String(id).padStart(4, "0")}`;

// URL d'un ticket précis (modification / suppression).
// L'ID est d'abord converti et validé (entier strictement positif), puis encodé :
// une valeur inattendue (ex : "../stats") ne peut pas changer la route appelée.
// Retourne null si l'ID est invalide → l'appelant n'envoie aucune requête.
const ticketUrl = (ticketId) => {
  const id = Number(ticketId);
  if (!Number.isInteger(id) || id <= 0) return null;
  return `${API_URL}/api/tickets/${encodeURIComponent(id)}`;
};

// Message affiché (bandeau d'erreur existant) quand l'ID d'un ticket est invalide
const INVALID_TICKET_ID_ERROR = "Erreur : identifiant de ticket invalide";

function App() {
  const [tickets, setTickets] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [formData, setFormData] = useState({
    machine_name: "",
    description: "",
    priority: "Medium",
    assigned_to: "",
  });
  const [submitting, setSubmitting] = useState(false);

  const fetchTickets = () => {
    setLoading(true);
    fetch(`${API_URL}/api/tickets`)
      .then((res) => res.json())
      .then((data) => {
        setTickets(data);
        setLoading(false);
      })
      .catch((err) => {
        setError("Impossible de charger les tickets : " + err.message);
        setLoading(false);
      });
  };

  // Récupère les statistiques globales depuis /api/stats
  const fetchStats = () => {
    fetch(`${API_URL}/api/stats`)
      .then((res) => res.json())
      .then((data) => setStats(data))
      .catch(() => setStats(null)); // en cas d'erreur, on n'affiche juste pas les cartes
  };

  useEffect(() => {
    fetchTickets();
    fetchStats();
  }, []);

  // Rafraîchit les tickets ET les stats ensemble (utilisé après chaque action)
  const refreshAll = () => {
    fetchTickets();
    fetchStats();
  };

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setSubmitting(true);
    fetch(`${API_URL}/api/tickets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...formData,
        assigned_to: formData.assigned_to || null,
      }),
    })
      .then((res) => {
        if (!res.ok) throw new Error("Erreur lors de la création");
        return res.json();
      })
      .then(() => {
        setFormData({ machine_name: "", description: "", priority: "Medium", assigned_to: "" });
        refreshAll();
        setSubmitting(false);
      })
      .catch((err) => {
        setError("Erreur : " + err.message);
        setSubmitting(false);
      });
  };

  const handleStatusChange = (ticketId, newStatus) => {
    const url = ticketUrl(ticketId);
    if (!url) {
      // ID invalide : aucune requête envoyée, erreur affichée comme les autres
      setError(INVALID_TICKET_ID_ERROR);
      return;
    }
    fetch(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus }),
    })
      .then((res) => {
        if (!res.ok) throw new Error("Erreur lors de la mise à jour");
        return res.json();
      })
      .then(() => refreshAll())
      .catch((err) => setError("Erreur : " + err.message));
  };

  const handleDelete = (ticketId) => {
    const url = ticketUrl(ticketId);
    if (!url) {
      // Vérifié AVANT la confirmation : inutile de demander de confirmer
      // une suppression qui ne pourra pas être envoyée
      setError(INVALID_TICKET_ID_ERROR);
      return;
    }
    if (!window.confirm("Supprimer ce ticket définitivement ?")) return;
    fetch(url, { method: "DELETE" })
      .then((res) => {
        if (!res.ok) throw new Error("Erreur lors de la suppression");
        refreshAll();
      })
      .catch((err) => setError("Erreur : " + err.message));
  };

  return (
    <div
      className="min-h-screen bg-blueprint-50 font-body"
      style={{
        backgroundImage:
          "linear-gradient(rgba(29,78,116,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(29,78,116,0.05) 1px, transparent 1px)",
        backgroundSize: "32px 32px",
      }}
    >
      <div className="max-w-5xl mx-auto py-10 px-6">

        {/* ===== En-tête façon cartouche de plan technique ===== */}
        <header className="bg-blueprint-900 text-white rounded-sm shadow-lg mb-8 overflow-hidden">
          <div className="px-6 py-5 flex items-center justify-between border-b border-blueprint-700">
            <div>
              <p className="font-display uppercase tracking-[0.2em] text-xs text-blueprint-200">
                Leoni — Wiring Systems
              </p>
              <h1 className="font-display uppercase text-2xl md:text-3xl tracking-wide">
                Maintenance Ticketing System
              </h1>
            </div>
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-signal opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-signal"></span>
              </span>
              <span className="font-mono text-xs uppercase tracking-widest text-blueprint-200">Live</span>
            </div>
          </div>
          <div className="grid grid-cols-3 divide-x divide-blueprint-700 font-mono text-xs">
            <div className="px-6 py-3">
              <p className="text-blueprint-200 uppercase tracking-widest">Site</p>
              <p className="text-white mt-1">Leoni — Sousse</p>
            </div>
            <div className="px-6 py-3">
              <p className="text-blueprint-200 uppercase tracking-widest">Ligne</p>
              <p className="text-white mt-1">Toutes lignes</p>
            </div>
            <div className="px-6 py-3">
              <p className="text-blueprint-200 uppercase tracking-widest">Tickets ouverts</p>
              <p className="text-white mt-1">
                {tickets.filter((t) => t.status === "Open").length} actif(s)
              </p>
            </div>
          </div>
        </header>

        {/* ===== Cartes KPI — vue d'ensemble statistique ===== */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <div className="bg-white rounded-sm shadow-sm border border-blueprint-200 border-t-4 border-t-red-signal p-4">
              <p className="text-steel-400 text-xs uppercase tracking-widest font-mono">Ouverts</p>
              <p className="font-display text-3xl text-blueprint-900 mt-1">{stats.open_tickets}</p>
            </div>
            <div className="bg-white rounded-sm shadow-sm border border-blueprint-200 border-t-4 border-t-amber-signal p-4">
              <p className="text-steel-400 text-xs uppercase tracking-widest font-mono">En cours</p>
              <p className="font-display text-3xl text-blueprint-900 mt-1">{stats.in_progress_tickets}</p>
            </div>
            <div className="bg-white rounded-sm shadow-sm border border-blueprint-200 border-t-4 border-t-blueprint-700 p-4">
              <p className="text-steel-400 text-xs uppercase tracking-widest font-mono">Priorité Haute</p>
              <p className="font-display text-3xl text-blueprint-900 mt-1">{stats.high_priority_tickets}</p>
            </div>
            <div className="bg-white rounded-sm shadow-sm border border-blueprint-200 border-t-4 border-t-green-signal p-4">
              <p className="text-steel-400 text-xs uppercase tracking-widest font-mono">Résolution Moy.</p>
              <p className="font-display text-3xl text-blueprint-900 mt-1">
                {stats.avg_resolution_time_hours !== null
                  ? `${stats.avg_resolution_time_hours}h`
                  : "—"}
              </p>
            </div>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border-l-4 border-red-signal text-red-signal px-4 py-3 rounded-sm mb-6 font-mono text-sm">
            {error}
          </div>
        )}

        {/* ===== Formulaire — "Nouvel ordre de travail" ===== */}
        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-sm shadow-sm border border-blueprint-200 mb-8"
        >
          <div className="border-l-4 border-amber-signal px-6 py-4">
            <h2 className="font-display uppercase tracking-wide text-blueprint-900 text-lg">
              Nouvel ordre de travail
            </h2>
            <p className="text-steel-400 text-sm">Signaler un problème sur une machine</p>
          </div>
          <div className="px-6 pb-6 grid grid-cols-1 md:grid-cols-4 gap-4">
            <input
              type="text" name="machine_name" placeholder="Nom de la machine"
              value={formData.machine_name} onChange={handleChange} required
              className="border border-blueprint-200 rounded-sm px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blueprint-700"
            />
            <input
              type="text" name="description" placeholder="Description du problème"
              value={formData.description} onChange={handleChange} required
              className="border border-blueprint-200 rounded-sm px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blueprint-700 md:col-span-2"
            />
            <select
              name="priority" value={formData.priority} onChange={handleChange}
              className="border border-blueprint-200 rounded-sm px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blueprint-700"
            >
              <option value="Low">Low</option>
              <option value="Medium">Medium</option>
              <option value="High">High</option>
            </select>
            <input
              type="text" name="assigned_to" placeholder="Assigné à (optionnel)"
              value={formData.assigned_to} onChange={handleChange}
              className="border border-blueprint-200 rounded-sm px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blueprint-700 md:col-span-3"
            />
            <button
              type="submit" disabled={submitting}
              className="bg-blueprint-900 hover:bg-blueprint-700 disabled:opacity-50 text-white font-display uppercase tracking-wide text-sm px-6 py-2 rounded-sm transition-colors"
            >
              {submitting ? "Création..." : "Créer l'ordre"}
            </button>
          </div>
        </form>

        {/* ===== Liste des ordres de travail ===== */}
        <div className="bg-white rounded-sm shadow-sm border border-blueprint-200 overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="bg-blueprint-900 text-blueprint-200 font-display uppercase tracking-wide text-xs">
              <tr>
                <th className="px-4 py-3">Ref.</th>
                <th className="px-4 py-3">Machine</th>
                <th className="px-4 py-3">Description</th>
                <th className="px-4 py-3">Priorité</th>
                <th className="px-4 py-3">Statut</th>
                <th className="px-4 py-3">Technicien</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan="7" className="px-4 py-8 text-center text-steel-400 font-mono text-xs">Chargement...</td></tr>
              )}
              {!loading && tickets.length === 0 && (
                <tr><td colSpan="7" className="px-4 py-8 text-center text-steel-400 font-mono text-xs">Aucun ordre de travail en cours</td></tr>
              )}
              {!loading && tickets.map((ticket) => (
                <tr key={ticket.id} className="border-b border-blueprint-100 hover:bg-blueprint-50 transition-colors">
                  <td className="px-4 py-3 font-mono text-blueprint-700">{formatWorkOrder(ticket.id)}</td>
                  <td className="px-4 py-3 font-medium text-blueprint-900">{ticket.machine_name}</td>
                  <td className="px-4 py-3 text-steel-400">{ticket.description}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-2 font-mono text-xs uppercase text-blueprint-900">
                      <span className={`h-2 w-2 rounded-full ${PRIORITY_DOT[ticket.priority]}`}></span>
                      {ticket.priority}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <select
                      value={ticket.status}
                      onChange={(e) => handleStatusChange(ticket.id, e.target.value)}
                      className={`px-2 py-1 rounded-sm text-xs font-mono uppercase cursor-pointer border-0 ${STATUS_STYLES[ticket.status]}`}
                    >
                      {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </td>
                  <td className="px-4 py-3 text-steel-400">
                    {ticket.assigned_to || <span className="text-blueprint-200">—</span>}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleDelete(ticket.id)}
                      className="text-red-signal hover:bg-red-50 h-7 w-7 rounded-sm text-sm font-bold"
                      aria-label="Supprimer"
                    >
                      ×
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default App;