from decimal import Decimal, ROUND_HALF_UP

CALCULATION_VERSION=2

def dec(v): return Decimal(str(v or 0))
def pct(a,b):
    if dec(b)<=0: return None
    return (dec(a)/dec(b)*Decimal("100")).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)

def calculate_supplier_performance(cursor,supplier_id):
    cursor.execute("""SELECT p.id AS procurement_id,sc.id AS commitment_id,sc.promised_qty,sc.delivery_end,
                              d.id AS delivery_id,d.delivery_date,i.id AS inspection_id,i.result,i.received_qty
                       FROM procurements p JOIN purchase_orders po ON po.procurement_id=p.id
                       JOIN supplier_commitments sc ON sc.purchase_order_id=po.id AND sc.supplier_id=%s
                       LEFT JOIN deliveries d ON d.commitment_id=sc.id
                       LEFT JOIN inspections i ON i.delivery_id=d.id
                       WHERE p.status='COMPLETED' ORDER BY p.id,sc.id,d.id,i.id""",(supplier_id,))
    rows=cursor.fetchall()
    by_proc={}
    for r in rows:
        obs=by_proc.setdefault(r["procurement_id"],{"commitments":{},"timing":[] ,"quality":[]})
        obs["commitments"].setdefault(r["commitment_id"],dec(r["promised_qty"]))
        if r["delivery_id"] and r["delivery_date"] and r["delivery_date"] > r["delivery_end"]:
            obs["timing"].append(False)
        elif r["delivery_id"] and r["delivery_date"]:
            obs["timing"].append(True)
        if r["inspection_id"]: obs["quality"].append(r["result"])
    observations=list(by_proc.values())
    if not observations:
        return {"supplier_id":supplier_id,"status":"NO_HISTORY","observation_count":0,"completed_procurement_count":0,"completed_commitment_count":0,"promised_quantity":Decimal("0"),"accepted_quantity":Decimal("0"),"fulfilment_rate":None,"quantity_variance_rate":None,"on_time_delivery_rate":None,"quality_acceptance_rate":None,"timing_observation_count":0,"quality_observation_count":0,"calculation_version":CALCULATION_VERSION}
    promised=sum((sum(o["commitments"].values(),Decimal("0")) for o in observations),Decimal("0"))
    accepted=Decimal("0")
    for procurement_id,o in by_proc.items():
        cursor.execute("""SELECT COALESCE(SUM(i.received_qty),0) AS accepted FROM supplier_commitments sc
                          JOIN purchase_orders po ON po.id=sc.purchase_order_id JOIN deliveries d ON d.commitment_id=sc.id
                          JOIN inspections i ON i.delivery_id=d.id WHERE po.procurement_id=%s AND sc.supplier_id=%s AND i.result='ACCEPTED'""",(procurement_id,supplier_id))
        accepted+=dec(cursor.fetchone()["accepted"])
    timing_obs=sum(1 for o in observations if o["timing"])
    on_time=sum(1 for o in observations if o["timing"] and all(o["timing"]))
    quality_obs=sum(1 for o in observations if o["quality"])
    quality_ok=sum(1 for o in observations if o["quality"] and all(x=="ACCEPTED" for x in o["quality"]))
    return {"supplier_id":supplier_id,"status":"AVAILABLE","observation_count":len(observations),"completed_procurement_count":len(observations),"completed_commitment_count":sum(len(o["commitments"]) for o in observations),"promised_quantity":promised,"accepted_quantity":accepted,"fulfilment_rate":pct(accepted,promised),"quantity_variance_rate":pct(abs(promised-accepted),promised),"on_time_delivery_rate":pct(on_time,timing_obs),"quality_acceptance_rate":pct(quality_ok,quality_obs),"timing_observation_count":timing_obs,"quality_observation_count":quality_obs,"calculation_version":CALCULATION_VERSION}

def save_supplier_performance(cursor,performance):
    cursor.execute("""INSERT INTO supplier_performance_metrics
      (supplier_id,observation_count,completed_procurement_count,completed_commitment_count,promised_quantity,accepted_quantity,
       fulfilment_rate,quantity_variance_rate,on_time_delivery_rate,quality_acceptance_rate,timing_observation_count,quality_observation_count,status,calculation_version,calculated_at)
      VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)
      ON CONFLICT(supplier_id) DO UPDATE SET observation_count=EXCLUDED.observation_count,completed_procurement_count=EXCLUDED.completed_procurement_count,
       completed_commitment_count=EXCLUDED.completed_commitment_count,promised_quantity=EXCLUDED.promised_quantity,accepted_quantity=EXCLUDED.accepted_quantity,
       fulfilment_rate=EXCLUDED.fulfilment_rate,quantity_variance_rate=EXCLUDED.quantity_variance_rate,on_time_delivery_rate=EXCLUDED.on_time_delivery_rate,
       quality_acceptance_rate=EXCLUDED.quality_acceptance_rate,timing_observation_count=EXCLUDED.timing_observation_count,quality_observation_count=EXCLUDED.quality_observation_count,
       status=EXCLUDED.status,calculation_version=EXCLUDED.calculation_version,calculated_at=CURRENT_TIMESTAMP RETURNING *""",
      (performance["supplier_id"],performance["observation_count"],performance["completed_procurement_count"],performance["completed_commitment_count"],performance["promised_quantity"],performance["accepted_quantity"],performance["fulfilment_rate"],performance["quantity_variance_rate"],performance["on_time_delivery_rate"],performance["quality_acceptance_rate"],performance["timing_observation_count"],performance["quality_observation_count"],performance["status"],performance["calculation_version"]))
    return cursor.fetchone()
