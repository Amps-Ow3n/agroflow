import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getProcurements } from "../../api/procurementApi";
import { Page, Loading, Empty, Status } from "../../components/common/Page";
export default function SchoolDashboardPage(){
 const [data,setData]=useState([]);const [loading,setLoading]=useState(true);
 useEffect(()=>{getProcurements().then(r=>setData(r.procurements||[])).finally(()=>setLoading(false));},[]);
 const counts=data.reduce((acc,item)=>{acc[item.status]=(acc[item.status]||0)+1;return acc;},{});
 return <Page title="School procurement" subtitle="Track requirements, supplier decisions, orders and outcomes." actions={<Link className="btn btn-dark" to="/school/procurements/new">New procurement</Link>}>
 {loading?<Loading/>:<><div className="row g-3 mb-4">{["DRAFT","SUBMITTED","EVALUATION","SELECTED","ORDERED","COMPLETED"].map(s=><div className="col-6 col-lg-2" key={s}><div className="card border-0 shadow-sm p-3"><div className="small text-muted">{s}</div><div className="fs-3 fw-bold">{counts[s]||0}</div></div></div>)}</div>
 <div className="card border-0 shadow-sm"><div className="card-body"><h5>Recent procurements</h5>{data.length===0?<Empty>No procurement records yet.</Empty>:<div className="table-responsive"><table className="table align-middle"><tbody>{data.slice(0,8).map(p=><tr key={p.id}><td><Link to={`/school/procurements/${p.id}`}>{p.procurement_identifier||`Procurement #${p.id}`}</Link><div className="small text-muted">{p.title}</div></td><td><Status value={p.status}/></td><td>{p.required_by_date||"—"}</td></tr>)}</tbody></table></div>}</div></div></>}
 </Page>;
}
