"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { 
  Building, 
  CheckCircle, 
  AlertCircle, 
  Clock, 
  RefreshCw,
  Upload,
  FileSpreadsheet,
  Search
} from "lucide-react";

// Types
interface Cabinet {
  id: number;
  nom: string;
  identifiant: string;
  email: string;
  immatriculation: string;
  statut: string;
  completude: number;
  respondent_id: number;
  created_at: string;
}

interface Stats {
  total_cabinets: number;
  total_documents: number;
  complet: number;
  incomplete: number;
  pending: number;
}

export default function Dashboard() {
  const [cabinets, setCabinets] = useState<Cabinet[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");

  // Fetch data
  const fetchData = async () => {
    setLoading(true);
    try {
      // Fetch stats
      const statsRes = await fetch("/api/stats");
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }
      
      // Fetch cabinets
      const cabinetsRes = await fetch("/api/cabinets");
      if (cabinetsRes.ok) {
        const data = await cabinetsRes.json();
        setCabinets(data);
      }
    } catch (err) {
      console.error("Fetch error:", err);
    }
    setLoading(false);
  };

  // Scan EvalAndGo
  const handleScan = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/scan-evalandgo");
      if (res.ok) {
        const result = await res.json();
        alert(`Scanné: ${result.scanned} répondants, ${result.created} créés, ${result.updated} mis à jour`);
        await fetchData();
      }
    } catch (err) {
      console.error("Scan error:", err);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Filter cabinets
  const filteredCabinets = cabinets.filter((c) => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      c.nom?.toLowerCase().includes(s) ||
      c.email?.toLowerCase().includes(s) ||
      c.identifiant?.toLowerCase().includes(s)
    );
  });

  // Get status color
  const getStatusBadge = (completude: number) => {
    if (completude >= 80) {
      return <span className="badge badge-success">Complet</span>;
    }
    if (completude > 0) {
      return <span className="badge badge-warning">Incomplet</span>;
    }
    return <span className="badge badge-error">En attente</span>;
  };

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Building className="w-8 h-8 text-blue-600" />
            <h1 className="text-xl font-bold text-gray-900">
              MustCompliance
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleScan}
              disabled={loading}
              className="btn btn-primary flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              Scanner EvalAndGo
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-4 gap-4 mb-6">
            <div className="card">
              <div className="text-2xl font-bold">{stats.total_cabinets}</div>
              <div className="text-sm text-gray-500">Total Cabinets</div>
            </div>
            <div className="card">
              <div className="text-2xl font-bold text-green-600">
                {stats.complet}
              </div>
              <div className="text-sm text-gray-500">Complets</div>
            </div>
            <div className="card">
              <div className="text-2xl font-bold text-yellow-600">
                {stats.incomplete}
              </div>
              <div className="text-sm text-gray-500">Incomplets</div>
            </div>
            <div className="card">
              <div className="text-2xl font-bold text-gray-600">
                {stats.pending}
              </div>
              <div className="text-sm text-gray-500">En attente</div>
            </div>
          </div>
        )}

        {/* Search */}
        <div className="card mb-6">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Rechercher un cabinet..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg"
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2 mb-4">
          <button className="btn btn-secondary flex items-center gap-2">
            <FileSpreadsheet className="w-4 h-4" />
            Exporter Excel
          </button>
        </div>

        {/* Cabinets Table */}
        <div className="card overflow-hidden">
          <table className="table">
            <thead>
              <tr>
                <th>Cabinet</th>
                <th>Email</th>
                <th>ORIAS</th>
                <th>Complétude</th>
                <th>Statut</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filteredCabinets.map((cabinet) => (
                <tr key={cabinet.id}>
                  <td>
                    <div className="font-medium">{cabinet.nom}</div>
                    <div className="text-sm text-gray-500">
                      {cabinet.identifiant}
                    </div>
                  </td>
                  <td className="text-gray-600">{cabinet.email}</td>
                  <td className="text-gray-600">
                    {cabinet.immatriculation || "—"}
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <div className="progress-bar w-24">
                        <div
                          className="progress-fill"
                          style={{ width: `${cabinet.completude}%` }}
                        />
                      </div>
                      <span className="text-sm font-medium">
                        {cabinet.completude}%
                      </span>
                    </div>
                  </td>
                  <td>{getStatusBadge(cabinet.completude)}</td>
                  <td>
                    <Link
                      href={`/cabinet/${cabinet.id}`}
                      className="text-blue-600 hover:underline"
                    >
                      Voir →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          
          {filteredCabinets.length === 0 && (
            <div className="text-center py-8 text-gray-500">
              {loading ? "Chargement..." : "Aucun cabinet trouvé"}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}