"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { 
  ArrowLeft, 
  Upload, 
  CheckCircle, 
  XCircle,
  Building,
  Mail,
  Phone,
  FileText,
  AlertTriangle
} from "lucide-react";

// Types
interface Cabinet {
  id: number;
  nom: string;
  identifiant: string;
  email: string;
  telephone: string;
  immatriculation: string;
  numero_tva: string;
  informations: string;
  rgpd: string;
  lien_capitalistique: string;
  activites: any[];
  assurance: string;
  association: string;
  reclamations: string;
  communications: string;
  remunerations_incitations: string;
  representant_legaux: any[];
  statut: string;
  completude: number;
  documents_manquants: string[];
  created_at: string;
}

const REQUIRED_DOCS = [
  { code: "ORIAS", label: "Immatriculation ORIAS" },
  { code: "RGPD", label: "Politique RGPD" },
  { code: "RCP", label: "Responsabilité Civile Professionnelle" },
  { code: "Réclamations", label: "Procédure réclamations" },
  { code: "RCDA", label: "Rapport Conseil Déclaration d'Adéquation" },
  { code: "DER", label: "Document Entrée en Relation" },
  { code: "LM", label: "Lettre de Mission" },
  { code: "LCB-FT", label: "Fiche Vigilance AML" },
];

export default function CabinetPage() {
  const params = useParams();
  const [cabinet, setCabinet] = useState<Cabinet | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [docType, setDocType] = useState("");

  const cabinetId = params.id as string;

  // Fetch cabinet
  const fetchCabinet = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/cabinet/${cabinetId}`);
      if (res.ok) {
        const data = await res.json();
        setCabinet(data);
      }
    } catch (err) {
      console.error("Fetch error:", err);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchCabinet();
  }, [cabinetId]);

  // Upload document
  const handleUpload = async () => {
    if (!docType) return;
    
    setUploading(true);
    try {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = ".pdf,.doc,.docx,.jpg,.png";
      
      input.onchange = async (e: any) => {
        const file = e.target.files?.[0];
        if (!file) return;
        
        const formData = new FormData();
        formData.append("file", file);
        formData.append("doc_type", docType);
        
        const res = await fetch(`/api/cabinet/${cabinetId}/upload`, {
          method: "POST",
          body: formData,
        });
        
        if (res.ok) {
          alert("Document uploaded!");
          await fetchCabinet();
        }
      };
      
      input.click();
    } catch (err) {
      console.error("Upload error:", err);
    }
    setUploading(false);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        Loading...
      </div>
    );
  }

  if (!cabinet) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        Cabinet not found
      </div>
    );
  }

  // Determine which docs are present
  const presentDocs = REQUIRED_DOCS.map((doc) => ({
    ...doc,
    present: !cabinet.documents_manquants.includes(doc.code),
  }));

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to dashboard
          </Link>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex justify-between items-start mb-6">
          <div>
            <h1 className="text-2xl font-bold">{cabinet.nom}</h1>
            <p className="text-gray-500">{cabinet.identifiant}</p>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold">{cabinet.completude}%</div>
            <div className="text-sm text-gray-500">Completion</div>
          </div>
        </div>

        {/* Missing documents alert */}
        {cabinet.documents_manquants.length > 0 && (
          <div className="card border-l-4 border-l-yellow-500 mb-6">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-yellow-600 mt-0.5" />
              <div>
                <h3 className="font-medium">
                  {cabinet.documents_manquants.length} missing document(s)
                </h3>
              </div>
            </div>
          </div>
        )}

        {/* Grid */}
        <div className="grid grid-cols-3 gap-6">
          {/* Contact Info */}
          <div className="card">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <Building className="w-5 h-5" />
              Information
            </h2>
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Mail className="w-4 h-4 text-gray-400" />
                <span>{cabinet.email || "—"}</span>
              </div>
              <div className="flex items-center gap-2">
                <Phone className="w-4 h-4 text-gray-400" />
                <span>{cabinet.telephone || "—"}</span>
              </div>
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-gray-400" />
                <span>ORIAS: {cabinet.immatriculation || "—"}</span>
              </div>
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-gray-400" />
                <span>TVA: {cabinet.numero_tva || "—"}</span>
              </div>
            </div>
          </div>

          {/* Activities */}
          <div className="card">
            <h2 className="font-semibold mb-4">Activities</h2>
            <div className="flex flex-wrap gap-2">
              {cabinet.activites?.map((act: string) => (
                <span key={act} className="badge badge-success">
                  {act}
                </span>
              )) || "None"}
            </div>
          </div>

          {/* Upload */}
          <div className="card">
            <h2 className="font-semibold mb-4">Upload Document</h2>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className="w-full mb-2 p-2 border rounded"
            >
              <option value="">Select...</option>
              {REQUIRED_DOCS.map((doc) => (
                <option key={doc.code} value={doc.code}>
                  {doc.label}
                </option>
              ))}
            </select>
            <button
              onClick={handleUpload}
              disabled={!docType || uploading}
              className="btn btn-primary w-full flex items-center justify-center gap-2"
            >
              <Upload className="w-4 h-4" />
              {uploading ? "Loading..." : "Upload"}
            </button>
          </div>
        </div>

        {/* Documents */}
        <div className="card mt-6">
          <h2 className="font-semibold mb-4">Documents</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Document</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {presentDocs.map((doc) => (
                <tr key={doc.code}>
                  <td>{doc.label}</td>
                  <td>
                    {doc.present ? (
                      <span className="flex items-center gap-2 text-green-600">
                        <CheckCircle className="w-4 h-4" />
                        Present
                      </span>
                    ) : (
                      <span className="flex items-center gap-2 text-red-600">
                        <XCircle className="w-4 h-4" />
                        Missing
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Details */}
        {(cabinet.rgpd || cabinet.assurance || cabinet.reclamations) && (
          <div className="card mt-6">
            <h2 className="font-semibold mb-4">Details</h2>
            <div className="space-y-4">
              {cabinet.rgpd && (
                <div>
                  <h3 className="font-medium text-gray-600 mb-1">RGPD</h3>
                  <p className="text-sm whitespace-pre-wrap">{cabinet.rgpd}</p>
                </div>
              )}
              {cabinet.assurance && (
                <div>
                  <h3 className="font-medium text-gray-600 mb-1">Insurance</h3>
                  <p className="text-sm whitespace-pre-wrap">{cabinet.assurance}</p>
                </div>
              )}
              {cabinet.reclamations && (
                <div>
                  <h3 className="font-medium text-gray-600 mb-1">Claims</h3>
                  <p className="text-sm whitespace-pre-wrap">{cabinet.reclamations}</p>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}