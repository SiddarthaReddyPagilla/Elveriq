/* Elveriq inbound + operations center. Scoped browser data, no external credentials. */
(() => {
  'use strict';
  const root = document.getElementById('workspace');
  if (!root || root.dataset.demo === 'true') return;
  const canManage = ['owner', 'manager'].includes(root.dataset.role);
  const el = id => document.getElementById(id);
  const safe = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  let notices = [], purchases = [], cases = [], shipments = [], warehouses = [];
  const retries = new Map();
  async function api(path, method, payload, key) {
    const response = await fetch('/api' + path, {
      credentials: 'same-origin', method: method || 'GET',
      headers: {'Content-Type':'application/json','X-CSRF-Token':csrf,...(key ? {'Idempotency-Key':key} : {})},
      ...(method ? {body:JSON.stringify(payload || {})} : {})
    });
    const data = await response.json().catch(() => ({error:'Unexpected server response'}));
    if (!response.ok) throw new Error(data.error || (Array.isArray(data.detail) ? data.detail[0]?.msg : data.detail) || `HTTP ${response.status}`);
    return data;
  }
  function report(message, isError = false) {
    const text=el('ops-notice');
    if (text) {text.textContent=message; text.style.color=isError ? 'var(--danger, #b33434)' : 'inherit';}
    const main=el('notice');
    if (main) {main.textContent=message; main.className=`alert ${isError ? 'error' : 'success'}`;}
  }
  function options(select, rows, value, label) {
    if (!select) return;
    const old = select.value;
    select.innerHTML=rows.map(row=>`<option value="${safe(value(row))}">${safe(label(row))}</option>`).join('');
    if (rows.some(row=>String(value(row))===old)) select.value=old;
  }
  function table(target, headers, rows) {
    if (!el(target)) return;
    el(target).innerHTML = rows.length
      ? `<table><thead><tr>${headers.map(x=>`<th>${safe(x)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table>`
      : '<div class="empty-state">No records in this workspace.</div>';
  }
  function refreshPoLines() {
    const po=purchases.find(p=>p.id===Number(el('asn-po-select')?.value));
    const lines=(po?.items||[]).filter(x=>x.outstanding>0);
    options(el('asn-line-select'), lines, x=>x.line_id, x=>`${x.sku} · ${x.outstanding} unreceived`);
    const qty=el('asn-create-form')?.elements.expected;
    if (qty) {const l=lines.find(x=>x.line_id===Number(el('asn-line-select').value)); qty.max=String(l?.outstanding||1);}
  }
  function refreshScanLines() {
    const n=notices.find(row=>row.id===Number(el('asn-scan-notice')?.value));
    const lines=(n?.items||[]).filter(row=>row.short>0);
    options(el('asn-scan-line'), lines, row=>row.id, row=>`${row.sku} · ${row.short} remaining`);
  }
  async function load() {
    try {
      [notices,purchases,cases,shipments,warehouses]=await Promise.all([
        api('/inbound/notices'),api('/purchase-orders'),api('/exceptions'),
        api('/shipping/tracking'),api('/warehouses')]);
      const metric=await api('/operations/metrics');
      for (const [target,key] of [['ops-kpi-open','open_exceptions'],['ops-kpi-overdue','overdue_exceptions'],
        ['ops-kpi-inbound','arrived_asns'],['ops-kpi-staged','picked_staged_units']]) if(el(target)) el(target).textContent=metric[key].toLocaleString();
      options(el('asn-po-select'),purchases.filter(p=>['ordered','partial'].includes(p.status)),
        p=>p.id,p=>`#${p.id} · ${p.reference}`);
      refreshPoLines();
      options(el('asn-scan-notice'),notices.filter(n=>n.status==='arrived' && n.short>0),
        n=>n.id,n=>`${n.reference} · ${n.short} units to inspect`);
      refreshScanLines();
      options(el('ops-shipment-select'),shipments.filter(s=>s.milestone!=='delivered'),
        s=>s.shipment_id,s=>`#${s.shipment_id} · ${s.tracking_reference}`);
      const caseForm=el('ops-case-form');
      options(caseForm?.elements.warehouse_id,warehouses,w=>w.id,w=>w.name);
      table('asn-table',['ASN','PO / dock','Expected','Accepted','Damaged','Short','Status','Actions'],
        notices.map(n=>`<tr><td><strong>${safe(n.reference)}</strong><small>${safe(n.supplier_reference)}</small></td><td>PO #${n.purchase_order_id} / ${safe(n.dock||'—')}</td><td>${n.expected}</td><td>${n.accepted}</td><td>${n.damaged}</td><td>${n.short}</td><td>${safe(n.status)}</td><td><span class="task-actions">
          ${n.status==='planned' ? `<button class="link-button" data-asn="${n.id}" data-action="arrive">Arrived</button>` : ''}
          ${n.status==='arrived' ? `<button class="link-button" data-asn="${n.id}" data-action="select">Select scan</button>` : ''}
          ${canManage && n.status==='arrived' ? `<button class="link-button" data-asn="${n.id}" data-action="close">Close ASN</button>` : ''}
          <button class="link-button muted-link" data-asn="${n.id}" data-action="events">History</button>
        </span></td></tr>`));
      table('ops-exceptions-table',['Case','Source','Severity','Owner','Deadline','Status','Actions'],
        cases.map(c=>`<tr><td><strong>#${c.id}: ${safe(c.title)}</strong><small>${safe(c.category)}</small></td><td>${safe(c.source_type)} #${c.source_id||'—'}</td><td>${safe(c.severity)}</td><td>${c.assigned_user_id??'—'}</td><td>${safe(c.due_at.slice(0,16).replace('T',' '))}${c.overdue?' · OVERDUE':''}</td><td>${safe(c.status)}</td><td><span class="task-actions">
          ${c.status==='open' ? `<button class="link-button" data-case="${c.id}" data-action="acknowledge">Acknowledge</button>` : ''}
          ${canManage && c.status!=='resolved' ? `<button class="link-button" data-case="${c.id}" data-action="assign">Assign</button><button class="link-button" data-case="${c.id}" data-action="resolve">Resolve</button>` : ''}
          ${canManage && c.status==='resolved' ? `<button class="link-button" data-case="${c.id}" data-action="reopen">Reopen</button>` : ''}
          <button class="link-button muted-link" data-case="${c.id}" data-action="history">History</button>
        </span></td></tr>`));
      table('ops-tracking-table',['Shipment','Carrier','Reference','Manually reported milestone','Updated','Action'],
        shipments.map(s=>`<tr><td>#${s.shipment_id}</td><td>${safe(s.carrier)}</td><td>${safe(s.tracking_reference)}</td><td>${safe(s.milestone)}</td><td>${safe(s.latest_at.slice(0,16).replace('T',' '))}</td><td><a class="link-button" href="/api/outbound/orders/${s.order_id}/manifest.csv">Manifest CSV</a> <button class="link-button muted-link" data-track="${s.shipment_id}">History</button></td></tr>`));
    } catch(err) {report(err.message,true);}
  }
  async function action(fn) {try {await fn();await load();}catch(err){report(err.message,true);}}
  async function submitRetry(formId,path,build,verb='POST') {
    const form=el(formId);if (!form) return;
    form.addEventListener('submit',async event=>{
      event.preventDefault();const d=new FormData(form);const body=build(d);
      const serialized=JSON.stringify({path:path(body),body});
      let state=retries.get(formId);
      if(!state || state.serialized!==serialized) state={serialized,key:crypto.randomUUID()};
      retries.set(formId,state);
      await action(async()=>{
        const result=await api(path(body),verb,body,state.key);
        retries.delete(formId);report(`Recorded #${result.id} successfully${result.replayed?' (replayed safely)':''}.`);
        form.reset();
      });
    });
  }
  if(el('asn-po-select')) el('asn-po-select').addEventListener('change',refreshPoLines);
  if(el('asn-line-select')) el('asn-line-select').addEventListener('change',refreshPoLines);
  if(el('asn-scan-notice')) el('asn-scan-notice').addEventListener('change',refreshScanLines);
  if(el('asn-create-form')) el('asn-create-form').addEventListener('submit',event=>{
    event.preventDefault();const form=event.currentTarget;const d=new FormData(form);
    action(async()=>{
      const r=await api('/inbound/notices','POST',{
        purchase_order_id:Number(d.get('purchase_order_id')),
        reference:d.get('reference'),supplier_reference:d.get('supplier_reference'),dock:d.get('dock'),
        items:[{purchase_line_id:Number(d.get('purchase_line_id')),expected:Number(d.get('expected'))}]});
      report(`ASN ${r.reference} created.`);form.reset();
    });
  });
  if(el('asn-scan-form')) submitRetry('asn-scan-form',d=>`/inbound/notices/${d.notice_id}/scan`,d=>({
    notice_id:Number(d.get('notice_id')),line_id:Number(d.get('line_id')),
    scan_sku:d.get('scan_sku'),accepted:Number(d.get('accepted')),
    damaged:Number(d.get('damaged')),damage_note:d.get('damage_note')}));
  if(el('ops-case-form')) submitRetry('ops-case-form',()=>'/exceptions',d=>({
    warehouse_id:Number(d.get('warehouse_id')),severity:d.get('severity'),
    title:d.get('title'),detail:d.get('detail')}));
  if(el('ops-milestone-form')) submitRetry('ops-milestone-form',d=>`/shipping/shipments/${d.shipment_id}/events`,d=>({
    shipment_id:Number(d.get('shipment_id')),milestone:d.get('milestone'),
    location:d.get('location'),note:d.get('note')}));
  el('asn-table')?.addEventListener('click',event=>{
    const b=event.target.closest('[data-asn]');if(!b)return;
    const id=Number(b.dataset.asn),mode=b.dataset.action;
    action(async()=>{
      if(mode==='select'){el('asn-scan-notice').value=String(id);refreshScanLines();el('asn-scan-sku').focus();return;}
      if(mode==='events'){const entries=await api(`/inbound/notices/${id}/events`);report(entries.map(e=>`${e.action}: ${e.note}`).join(' | ')||'No history');return;}
      if(mode==='close'){
        const note=window.prompt('Closure reason (required for shortages):','');if(note===null)return;
        await api(`/inbound/notices/${id}/close`,'POST',{note});report(`ASN #${id} closed.`);return;
      }
      if(mode==='arrive'){await api(`/inbound/notices/${id}/arrive`,'POST',{});report(`ASN #${id} arrived.`);}
    });
  });
  el('ops-exceptions-table')?.addEventListener('click',event=>{
    const b=event.target.closest('[data-case]');if(!b)return;
    const id=Number(b.dataset.case),mode=b.dataset.action;
    action(async()=>{
      if(mode==='history'){const entries=await api(`/exceptions/${id}/events`);report(entries.map(e=>`${e.action}: ${e.note}`).join(' | ')||'No events');return;}
      if(mode==='assign'){
        const users=await api('/tasks/assignees');
        const optionList=users.map(u=>`#${u.id} ${u.email}`).join(', ');
        const selected=window.prompt(`Assign to a staff user ID: ${optionList}`,'');
        if(selected===null)return;await api(`/exceptions/${id}/assign`,'POST',{user_id:Number(selected)});report(`Case #${id} assigned.`);return;
      }
      if(mode==='resolve'||mode==='reopen'){
        const note=window.prompt(`Reason for ${mode} (required):`,'');
        if(note===null)return;await api(`/exceptions/${id}/${mode}`,'POST',{note});report(`Case #${id} ${mode}d.`);return;
      }
      if(mode==='acknowledge'){await api(`/exceptions/${id}/acknowledge`,'POST',{});report(`Case #${id} acknowledged.`);}
    });
  });
  el('ops-tracking-table')?.addEventListener('click',event=>{
    const b=event.target.closest('[data-track]');if(!b)return;
    action(async()=>{
      const entries=await api(`/shipping/shipments/${Number(b.dataset.track)}/events`);
      report(entries.map(e=>`${e.milestone}: ${e.location}${e.note?' · '+e.note:''}`).join(' | ')||'No manual events yet');
    });
  });
  document.querySelectorAll('[data-section="inbound"],[data-section="exceptions"],[data-section="shipping"]').forEach(button=>
    button.addEventListener('click',load));
  const reportTypes = [
    ['inventory-health', 'Inventory health'], ['bin-capacity', 'Storage bin capacity'],
    ['receiving-quality', 'Inbound receiving quality'], ['purchase-backlog', 'Purchase backlog'],
    ['picking-pipeline', 'Picking execution'], ['packing-pipeline', 'Packing execution'],
    ['dispatch-activity', 'Dispatch volume'], ['delivery-visibility', 'Manual delivery visibility'],
    ['incident-risk', 'Incident exposure'], ['workforce-load', 'Workforce queue']
  ];
  async function refreshReports() {
    const target=el('ops-report-tiles'), status=el('ops-report-notice');
    if (!target) return;
    if (status) status.textContent='Reading live warehouse records…';
    const wid=el('ops-report-warehouse')?.value;
    const suffix=wid ? `?warehouse_id=${encodeURIComponent(wid)}` : '';
    try {
      const data=await Promise.all(reportTypes.map(([name])=>api(`/reports/${name}${suffix}`)));
      const rows=[];
      for (let i=0; i<data.length; i++) {
        const [name,label]=reportTypes[i];
        for (const [key,value] of Object.entries(data[i])) {
          if (key==='source' || key==='warehouse_id') continue;
          const shown=value!==null && typeof value==='object' ? JSON.stringify(value) : String(value);
          rows.push(`<tr><td>${safe(label)}</td><td>${safe(key.replaceAll('_',' '))}</td><td>${safe(shown)}</td></tr>`);
        }
      }
      table('ops-report-tiles',['Operational area','Metric','Live value'],rows);
      if (status) status.textContent=`${data.length} reports refreshed. Shipment events are manual entries, not carrier-verified.`;
    } catch(error) {
      if (status) status.textContent=error.message;
    }
  }
  document.querySelector('[data-section="reports"]')?.addEventListener('click', async()=>{
    const choices=el('ops-report-warehouse');
    try {
      const available=await api('/warehouses');
      if (choices) {
        const previous=choices.value;
        choices.innerHTML='<option value="">All warehouses</option>'+available.map(w=>
          `<option value="${Number(w.id)}">${safe(w.name)}</option>`).join('');
        if ([...choices.options].some(option=>option.value===previous)) choices.value=previous;
      }
      await refreshReports();
    } catch(error) {if (el('ops-report-notice')) el('ops-report-notice').textContent=error.message;}
  });
  el('ops-report-refresh')?.addEventListener('click',refreshReports);
  el('ops-report-warehouse')?.addEventListener('change',refreshReports);
  load();
})();
