import { useEffect, useState } from "react";
import { getMySupplier, addSupplierProduct, addSupplierCapability } from "../../api/supplierApi";
import { getApiError } from "../../utils/errors";
import { Page, Loading, Alert } from "../../components/common/Page";

export default function ProfilePage() {
  const [data, setData] = useState(null);
  const [product, setProduct] = useState("");
  const [capability, setCapability] = useState("");
  const [error, setError] = useState("");

  async function load() {
    try { setData(await getMySupplier()); }
    catch (err) { setError(getApiError(err)); }
  }

  useEffect(() => { load(); }, []);

  async function addProduct() {
    if (!product.trim()) return;
    try { await addSupplierProduct(product.trim()); setProduct(""); await load(); }
    catch (err) { setError(getApiError(err)); }
  }

  async function addCapability() {
    if (!capability.trim()) return;
    try { await addSupplierCapability(capability.trim()); setCapability(""); await load(); }
    catch (err) { setError(getApiError(err)); }
  }

  if (!data && !error) return <Page title="Supplier profile"><Loading /></Page>;

  const supplier = data?.supplier || {};

  return (
    <Page title="Supplier profile" subtitle="Maintain the supplier entity, not a supplier-user identity.">
      {error && <Alert>{error}</Alert>}
      <div className="card border-0 shadow-sm p-4 mb-3">
        <h5>{supplier.organization_name || supplier.supplier_code || "Supplier"}</h5>
        <div className="small text-muted">
          Verification: {supplier.verification_status || "—"} · Status: {supplier.status || "—"}
        </div>
      </div>
      <div className="row g-3">
        <div className="col-md-6">
          <div className="card border-0 shadow-sm p-3">
            <h6>Products</h6>
            {(data?.products || []).map((item) => <div key={item.id} className="border-bottom py-1">{item.product}</div>)}
            <div className="input-group mt-3">
              <input className="form-control" value={product} onChange={(e) => setProduct(e.target.value)} placeholder="Add product" />
              <button className="btn btn-dark" onClick={addProduct}>Add</button>
            </div>
          </div>
        </div>
        <div className="col-md-6">
          <div className="card border-0 shadow-sm p-3">
            <h6>Capabilities</h6>
            {(data?.capabilities || []).map((item) => <div key={item.id} className="border-bottom py-1">{item.capability}</div>)}
            <div className="input-group mt-3">
              <input className="form-control" value={capability} onChange={(e) => setCapability(e.target.value)} placeholder="Add capability" />
              <button className="btn btn-dark" onClick={addCapability}>Add</button>
            </div>
          </div>
        </div>
      </div>
    </Page>
  );
}
