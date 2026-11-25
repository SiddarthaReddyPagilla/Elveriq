/* Elveriq dock control: authenticated, no carrier promises or inventory mutation. */
(() => {
  'use strict';
  const root = document.querySelector('#dock-scheduler');
  if (!root) return;
  const canManage = ['owner','manager'].includes(document.getElementById('workspace')?.dataset.role);
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const id = name => document.getElementById(name);
  let doors = [], bookings = [], warehouses = [], lastId = null;
  async function api(path, method, body, key) {
    const r = await fetch('/api/dock' + path, {method:method||'GET', credentials:'same-origin',
      headers:{'Content-Type':'application/json','X-CSRF-Token':csrf,...(key?{'Idempotency-Key':key}:{})},
      ...(method ? {body:JSON.stringify(body)} : {})});
    const data = await r.json().catch(()=>({error:'Invalid server response'}));
    if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
    return data;
  }
  const note = (v, bad=false) => {id('dock-feedback').textContent=v; id('dock-feedback').style.color=bad?'#b42318':'inherit';};
  function choices(el, rows, value, label) {if (!el) return; const previous=el.value;
    el.innerHTML=rows.map(row=>`<option value="${esc(value(row))}">${esc(label(row))}</option>`).join('');
    if(rows.some(x=>String(value(x))===previous))el.value=previous;}
  function render() {
    id('dock-door-table').innerHTML=doors.length?`<table><thead><tr><th>Code</th><th>Warehouse</th><th>Purpose</th></tr></thead><tbody>${doors.map(x=>`<tr><td>${esc(x.code)}</td><td>${x.warehouse_id}</td><td>${esc(x.purpose)}</td></tr>`).join('')}</tbody></table>`:'No dock doors registered.';
    id('dock-appointments-table').innerHTML=bookings.length?`<table><thead><tr><th>Reference</th><th>Door</th><th>Time (UTC)</th><th>Status</th><th>Action</th></tr></thead><tbody>${bookings.map(x=>`<tr><td>${esc(x.reference)}<small>${esc(x.carrier)}</small></td><td>${esc(doors.find(d=>d.id===x.door_id)?.code||x.door_id)}</td><td>${esc(x.start_at)} – ${esc(x.end_at)}</td><td>${esc(x.status)}</td><td>${x.status==='scheduled'?`<button data-dock-action="check-in" data-appt="${x.id}">Check in</button> ${canManage?`<button data-dock-action="cancel" data-appt="${x.id}">Cancel</button>`:''}`:x.status==='checked_in'?`<button data-dock-action="complete" data-appt="${x.id}">Complete</button>`:''} <button data-dock-action="events" data-appt="${x.id}">History</button></td></tr>`).join('')}</tbody></table>`:'No appointments yet.';
    const book=id('dock-book-form'), door=id('dock-door-form');
    for (const form of [book,door]) if (form) choices(form.elements.warehouse_id,warehouses,x=>x.id,x=>x.name);
    const match=doors.filter(d=>d.warehouse_id===Number(book?.elements.warehouse_id.value));
    if(book) choices(book.elements.door_id,match,x=>x.id,x=>x.code);
  }
  async function refresh(older=false) {
    try {
      const params = older && lastId ? `?limit=50&before_id=${lastId}` : '?limit=50';
      const [d,a,w,m] = await Promise.all([api('/doors'),api('/appointments'+params),fetch('/api/warehouses',{credentials:'same-origin'}).then(r=>r.json()),api('/metrics')]);
      doors=d; warehouses=w;
      bookings=older?bookings.concat(a):a;
      lastId=bookings.at(-1)?.id || null;
      id('dock-more').hidden=a.length<50;
      for(const [element,key] of [['dock-kpi-scheduled','scheduled'],['dock-kpi-in','checked_in'],['dock-kpi-done','completed'],['dock-kpi-missed','no_show']]) id(element).textContent=m[key];
      render();
    } catch(e) {note(e.message,true);}
  }
  const door=id('dock-door-form'); if(door) door.addEventListener('submit',async e=>{
    e.preventDefault(); try {await api('/doors','POST',Object.fromEntries(new FormData(door)));note('Door created');await refresh();}catch(err){note(err.message,true);}
  });
  const book=id('dock-book-form'); if(book) {
    book.elements.warehouse_id.addEventListener('change',render);
    book.addEventListener('submit',async e=>{
      e.preventDefault();const data=Object.fromEntries(new FormData(book));
      data.warehouse_id=Number(data.warehouse_id);data.door_id=Number(data.door_id);
      data.start_at=new Date(data.start_at).toISOString();data.end_at=new Date(data.end_at).toISOString();
      try {await api('/appointments','POST',data,crypto.randomUUID());note('Vehicle slot reserved');await refresh();}catch(err){note(err.message,true);}
    });
  }
  id('dock-appointments-table').addEventListener('click', async e=>{
    const button=e.target.closest('button[data-dock-action]');if(!button)return;
    const action=button.dataset.dockAction, aid=button.dataset.appt;
    try {
      if(action==='events') {const history=await api(`/appointments/${aid}/events`);
        note(history.map(x=>`${x.action}: ${x.note}`).join(' | ')||'No history');return;}
      const reason=action==='cancel'?prompt('Reason for cancellation (required):'):'';
      if(action==='cancel' && !reason?.trim())return;
      if(!confirm(`Confirm ${action} for appointment #${aid}?`))return;
      await api(`/appointments/${aid}/${action}`,'POST',{note:reason||''});note('Appointment updated');await refresh();
    }catch(err){note(err.message,true);}
  });
  id('dock-refresh').addEventListener('click',()=>refresh());
  id('dock-more').addEventListener('click',()=>refresh(true));
  refresh();
})();
