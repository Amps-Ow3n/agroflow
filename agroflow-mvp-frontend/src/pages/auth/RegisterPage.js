import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { register } from "../../api/authApi";
import { getApiError } from "../../utils/errors";

const schoolResponsibilities = ["ORGANIZATION_ADMIN","PROCUREMENT_OFFICER","PROCUREMENT_REVIEWER","RECEIVING_OFFICER"];
const supplierResponsibilities = ["ORGANIZATION_ADMIN","SUPPLIER_USER","SUPPLIER_ADMIN"];

export default function RegisterPage() {
  const [form,setForm]=useState({full_name:"",email:"",password:"",organization_name:"",organization_type:"SCHOOL",responsibility:"PROCUREMENT_OFFICER"});
  const [error,setError]=useState(""); const [success,setSuccess]=useState(""); const [busy,setBusy]=useState(false);
  const navigate=useNavigate();
  const responsibilities=form.organization_type==="SCHOOL"?schoolResponsibilities:supplierResponsibilities;
  function set(k,v){setForm(f=>({...f,[k]:v}));}
  function typeChange(v){set("organization_type",v);set("responsibility",v==="SCHOOL"?"PROCUREMENT_OFFICER":"SUPPLIER_USER");}
  async function submit(e){e.preventDefault();setError("");setSuccess("");setBusy(true);try{const r=await register(form);setSuccess(r.message||"Registration successful. You can now sign in.");setTimeout(()=>navigate("/login"),800);}catch(err){setError(getApiError(err,"Registration failed."));}finally{setBusy(false);}}
  return <div className="min-vh-100 d-flex align-items-center justify-content-center bg-light p-3">
    <form onSubmit={submit} className="card shadow-sm border-0 p-4" style={{width:500}}>
      <h2 className="fw-bold">Create organization</h2><p className="text-muted">Register the organization and first authorized user.</p>
      {error&&<div className="alert alert-danger">{error}</div>}{success&&<div className="alert alert-success">{success}</div>}
      {[
        ["full_name","Full name","text"],["email","Email","email"],["password","Password","password"],["organization_name","Organization name","text"]
      ].map(([k,l,t])=><div key={k} className="mb-3"><label className="form-label">{l}</label><input className="form-control" type={t} value={form[k]} onChange={e=>set(k,e.target.value)} required /></div>)}
      <label className="form-label">Organization type</label>
      <select className="form-select mb-3" value={form.organization_type} onChange={e=>typeChange(e.target.value)}><option>SCHOOL</option><option>SUPPLIER</option></select>
      <label className="form-label">Responsibility</label>
      <select className="form-select mb-3" value={form.responsibility} onChange={e=>set("responsibility",e.target.value)}>{responsibilities.map(x=><option key={x}>{x}</option>)}</select>
      <button className="btn btn-dark w-100" disabled={busy}>{busy?"Registering…":"Register"}</button>
      <div className="text-center mt-3 small"><Link to="/login">Back to sign in</Link></div>
    </form>
  </div>;
}
