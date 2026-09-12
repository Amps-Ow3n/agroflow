import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const links = {
  school: [
    ["/school", "Dashboard"],
    ["/school/procurements", "Procurements"],
    ["/school/procurements/new", "New Procurement"],
  ],
  supplier: [
    ["/supplier", "Dashboard"],
    ["/supplier/commitments", "Commitments"],
    ["/supplier/profile", "Supplier Profile"],
  ],
  admin: [
    ["/admin", "System Overview"],
  ],
};

export default function WorkspaceLayout({ type }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const nav = links[type] || [];

  return (
    <div className="d-flex min-vh-100 bg-light">
      <aside className="bg-white border-end p-3" style={{ width: 260 }}>
        <div className="fw-bold fs-5 mb-1">AgroFlow</div>
        <div className="small text-muted mb-4">
          {type === "school" ? "School procurement" : type === "supplier" ? "Supplier operations" : "System administration"}
        </div>
        <nav className="d-flex flex-column gap-1">
          {nav.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === `/${type}`} className={({isActive}) =>
              `text-decoration-none rounded-3 px-3 py-2 ${isActive ? "bg-dark text-white" : "text-secondary"}`
            }>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto pt-5">
          <div className="small text-muted mb-2">{user?.full_name || user?.name}</div>
          <button className="btn btn-outline-danger btn-sm w-100" onClick={() => { logout(); navigate("/login"); }}>
            Log out
          </button>
        </div>
      </aside>
      <main className="flex-grow-1 p-3 p-md-4 p-lg-5"><Outlet /></main>
    </div>
  );
}
