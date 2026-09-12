import React from "react";

export function Page({ title, subtitle, actions, children }) {
  return (
    <div>
      <div className="d-flex flex-wrap justify-content-between align-items-start gap-3 mb-4">
        <div>
          <h2 className="fw-bold mb-1">{title}</h2>
          {subtitle && <p className="text-muted mb-0">{subtitle}</p>}
        </div>
        {actions}
      </div>
      {children}
    </div>
  );
}
export function Alert({ children, type = "danger" }) {
  return <div className={`alert alert-${type}`}>{children}</div>;
}
export function Loading() {
  return <div className="text-muted py-4">Loading…</div>;
}
export function Empty({ children }) {
  return <div className="border rounded-3 bg-white p-4 text-muted">{children}</div>;
}
export function Status({ value }) {
  const cls = {
    DRAFT: "secondary", SUBMITTED: "info", EVALUATION: "warning", SELECTED: "primary",
    ORDERED: "primary", COMMITTED: "info", DELIVERY: "warning", INSPECTION: "warning",
    ACCEPTED: "success", COMPLETED: "success", CANCELLED: "danger",
    REJECTED: "danger",
  }[value] || "secondary";
  return <span className={`badge text-bg-${cls}`}>{value || "—"}</span>;
}
