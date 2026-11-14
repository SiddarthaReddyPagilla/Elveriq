/* Elveriq demo dashboard. No credentials or API keys are stored in this file. */
(() => {
  const root = document.getElementById('workspace');
  if (!root) return;
  const demo = root.dataset.demo === 'true';
  const role = root.dataset.role;
  const suffix = demo ? '?demo=true' : '';
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  let inventory = [], products = [], warehouses = [], orders = [], purchases = [];
  let locations = [], placedStock = [], workTasks = [], assignees = [];
  let outboundPicks = [], outboundCartons = [], outboundShipments = [], outboundLines = [];
  const currentUser = Number(root.dataset.userId || 0);
  const canManageWork = role === 'owner' || role === 'manager';

  if (role !== 'owner') document.querySelectorAll('.owner-only').forEach(el => el.remove());
  const byId = id => document.getElementById(id);
  const safe = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[ch]));
  const money = cents => '$' + (Number(cents) / 100).toFixed(2);
  const rowStatus = status => `<span class="status status-${safe(status)}">${safe(status)}</span>`;
  const table = (headers, rows) => rows.length
    ? `<table><thead><tr>${headers.map(h => `<th>${safe(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table>`
    : '<div class="empty-state">No records yet. Add your first item to get started.</div>';
  function notice(message, error = false) {
    const element = byId('notice');
    element.textContent = message;
    element.className = `alert ${error ? 'error' : 'success'}`;
    element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
  async function api(path, options = {}) {
    const response = await fetch(`/api${path}${options.method ? '' : suffix}`, {
      credentials: 'same-origin',
      ...options,
      headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
                 'X-CSRF-Token': csrf, ...(options.headers || {}) }
    });
    let data;
    try { data = await response.json(); } catch { data = {error: 'Unexpected server response'}; }
    if (!response.ok) throw new Error(data.error || data.detail?.[0]?.msg || `Request failed (${response.status})`);
    return data;
  }
  function refreshTaskBinOptions() {
    const form = byId('task-form'); if (!form) return;
    const kind = form.elements.kind.value;
    const wid = Number(form.elements.warehouse_id.value);
    const matching = locations.filter(b => b.warehouse_id === wid && b.active);
    const source = form.elements.from_bin_id;
    const dest = form.elements.to_bin_id;
    const sourceOld = source.value;
    const destOld = dest.value;
    source.disabled = kind === 'putaway';
    source.required = kind !== 'putaway';
    source.innerHTML = `<option value="">${kind === 'putaway' ? 'Unlocated stock' : 'Choose a source bin'}</option>` +
      matching.map(b => `<option value="${b.id}">${safe(b.code)}</option>`).join('');
    if (matching.some(b => String(b.id) === sourceOld)) source.value = sourceOld;
    dest.required = kind !== 'unlocate';
    dest.disabled = kind === 'unlocate';
    dest.innerHTML = kind === 'unlocate'
      ? '<option value="">UNLOCATED staging pool</option>'
      : '<option value="">Choose a destination bin</option>' + matching.map(b => `<option value="${b.id}">${safe(b.code)}</option>`).join('');
    if (kind !== 'unlocate' && matching.some(b => String(b.id) === destOld)) dest.value = destOld;
  }
  function refreshBinCountOptions() {
    const form = byId('bin-count-form'); if (!form) return;
    const warehouseId = Number(form.elements.warehouse_id.value);
    const select = form.elements.bin_id;
    const old = select.value;
    const choices = locations.filter(bin => bin.warehouse_id === warehouseId && bin.active);
    select.innerHTML = '<option value="">Select a physical bin</option>' +
      choices.map(bin => `<option value="${bin.id}">${safe(bin.code)}</option>`).join('');
    if (choices.some(bin => String(bin.id) === old)) select.value = old;
  }

  async function refreshOutboundOptions() {
    if (demo || !byId('out-carton-form')) return;
    const choices = orders.filter(o => o.status === 'reserved');
    document.querySelectorAll('.out-order-select, #out-plan-order').forEach(select => {
      const previous = select.value;
      select.innerHTML = choices.map(o => `<option value="${o.id}">#${o.id} · ${safe(o.customer_name)}</option>`).join('');
      if (choices.some(o => String(o.id) === previous)) select.value = previous;
    });
    await refreshOutboundLines();
  }
  async function refreshOutboundLines() {
    const orderId = Number(byId('out-plan-order')?.value);
    const lineSelect = byId('out-plan-line');
    if (!orderId || !lineSelect) return;
    const previous = lineSelect.value;
    outboundLines = await api(`/outbound/orders/${orderId}/lines`);
    lineSelect.innerHTML = outboundLines.map(l => `<option value="${l.order_line_id}">${safe(l.sku)} · ${l.planned}/${l.quantity} planned</option>`).join('');
    if (outboundLines.some(l => String(l.order_line_id) === previous)) lineSelect.value = previous;
    refreshOutboundBins();
  }
  function refreshOutboundBins() {
    const order = orders.find(o => o.id === Number(byId('out-plan-order')?.value));
    const line = outboundLines.find(l => l.order_line_id === Number(byId('out-plan-line')?.value));
    const select = byId('out-plan-bin');
    if (!select) return;
    const previous = select.value;
    const bins = placedStock.filter(b => b.warehouse_id === order?.warehouse_id &&
      b.sku === line?.sku && b.available > 0 && locations.some(l => l.id === b.bin_id && l.active));
    select.innerHTML = bins.map(b => `<option value="${b.bin_id}">${safe(b.bin_code)} · ${b.available} free</option>`).join('');
    if (bins.some(b => String(b.bin_id) === previous)) select.value = previous;
  }
  function renderOutbound() {
    if (demo || !byId('out-picks-table')) return;
    const stats = {
      'out-stat-open': outboundPicks.filter(p => ['queued','assigned','in_progress'].includes(p.status)).length,
      'out-stat-staged': outboundPicks.filter(p => ['picked','packed'].includes(p.status)).reduce((n,p) => n+p.quantity,0),
      'out-stat-sealed': outboundCartons.filter(c => c.status === 'sealed').length,
      'out-stat-shipped': outboundShipments.length
    };
    for (const [id, value] of Object.entries(stats)) byId(id).textContent = value.toLocaleString();
    byId('out-picks-table').innerHTML = table(['Order / Pick','SKU','Source bin','Units','Worker','Status','Actions'],
      outboundPicks.map(p => {
        const owned = currentUser === p.assigned_user_id;
        return `<tr><td><strong>Order #${p.order_id}</strong><small>Pick #${p.id}</small></td><td>${safe(p.sku)}</td><td>${safe(p.bin_code)}</td><td>${p.quantity}</td><td>${p.assigned_user_id ?? '—'}</td><td>${rowStatus(p.status)}</td><td><span class="task-actions">
          ${p.status === 'queued' ? `<button class="link-button" data-out-pick="${p.id}" data-out-action="claim">Claim</button>` : ''}
          ${p.status === 'assigned' && owned ? `<button class="link-button" data-out-pick="${p.id}" data-out-action="start">Start</button>` : ''}
          ${p.status === 'in_progress' && owned ? `<button class="link-button" data-out-pick="${p.id}" data-out-action="scan">Scan</button>` : ''}
          ${p.status === 'picked' ? `<button class="link-button" data-out-pick="${p.id}" data-out-action="pack">Pack</button>` : ''}
          ${canManageWork && ['queued','assigned','in_progress'].includes(p.status) ? `<button class="link-button muted-link" data-out-pick="${p.id}" data-out-action="cancel">Cancel</button>` : ''}
          <button class="link-button muted-link" data-out-pick="${p.id}" data-out-action="events">History</button></span></td></tr>`;
      }));
    byId('out-cartons-table').innerHTML = table(['Carton','Order','Contents','Status','Action'], outboundCartons.map(c =>
      `<tr><td><strong>${safe(c.code)}</strong><small>ID #${c.id}</small></td><td>#${c.order_id}</td><td>${c.items.map(i => `${safe(i.sku)} × ${i.quantity}`).join('<br>') || 'Empty'}</td><td>${rowStatus(c.status)}</td><td><span class="task-actions"><button class="link-button" data-out-carton="${c.id}" data-out-carton-action="select">Select</button>${c.status === 'open' && c.items.length ? `<button class="link-button" data-out-carton="${c.id}" data-out-carton-action="seal">Seal</button>` : ''}</span></td></tr>`));
    byId('out-shipments-table').innerHTML = table(['Shipment','Order','Carrier','Reference','Shipped at'],
      outboundShipments.map(s => `<tr><td>#${s.id}</td><td>#${s.order_id}</td><td>${safe(s.carrier)}</td><td>${safe(s.tracking_reference)}</td><td>${safe(s.shipped_at.slice(0,16).replace('T',' '))}</td></tr>`));
  }

  async function load() {
    try {
      const [overview, stock, productRows, warehouseRows, orderRows, movementRows, supplierRows, purchaseRows, transfers, counts, binCounts, returns, replenishment, team, planning, bins, binStocks, reconciliation, tasks, workerUsers] = await Promise.all([
        api('/overview'), api('/inventory'), api('/products'), api('/warehouses'),
        api('/orders'), api('/movements'), api('/suppliers'), api('/purchase-orders'),
        api('/transfers'), api('/cycle-counts'), api('/bin-cycle-counts'), api('/returns'), api('/replenishment'),
        role === 'owner' && !demo ? api('/staff') : Promise.resolve([]),
        api('/operations/queue'),
        api('/locations'), api('/locations/stock'), api('/locations/reconciliation'), api('/tasks'),
        canManageWork && !demo ? api('/tasks/assignees') : Promise.resolve([])
      ]);
      if (!demo) [outboundPicks, outboundCartons, outboundShipments] = await Promise.all([
        api('/outbound/picks'), api('/outbound/cartons'), api('/outbound/shipments')]);
      inventory = stock; products = productRows; warehouses = warehouseRows; orders = orderRows; purchases = purchaseRows;
      locations = bins; placedStock = binStocks; workTasks = tasks; assignees = workerUsers;
      const ids = {'stat-products': overview.products, 'stat-warehouses': overview.warehouses,
        'stat-stock': overview.on_hand, 'stat-reserved': overview.reserved,
        'stat-orders': overview.open_orders, 'stat-low': overview.low_stock,
        'stat-available': overview.on_hand - overview.reserved};
      for (const [id, value] of Object.entries(ids)) byId(id).textContent = Number(value).toLocaleString();
      const lows = stock.filter(r => r.low_stock);
      byId('alert-count').textContent = `${lows.length} alerts`;
      byId('low-stock-list').innerHTML = table(['Product', 'Location', 'Available'], lows.slice(0, 8).map(x =>
        `<tr><td><strong>${safe(x.name)}</strong><small>${safe(x.sku)}</small></td><td>${safe(x.warehouse)}</td><td><span class="status status-low">${x.available}</span></td></tr>`));
      byId('inventory-count').textContent = `${stock.length} location records`;
      byId('inventory-table').innerHTML = table(['Product / SKU', 'Location', 'On hand', 'Reserved', 'Available', 'Reorder at'], stock.map(x =>
        `<tr><td><strong>${safe(x.name)}</strong><small>${safe(x.sku)} · ${money(x.price_cents)}</small></td><td>${safe(x.warehouse)}</td><td>${x.on_hand}</td><td>${x.reserved}</td><td><strong class="${x.low_stock ? 'low-text' : ''}">${x.available}</strong></td><td>${x.reorder_point}</td></tr>`));
      byId('orders-table').innerHTML = table(['Order', 'Customer', 'Items', 'Due', 'Status', ''], orderRows.map(o =>
        `<tr><td>#${o.id}</td><td><strong>${safe(o.customer_name)}</strong></td><td>${o.items.map(i => `${safe(i.sku)} × ${i.quantity}`).join('<br>')}</td><td>${safe(o.due_date)}</td><td>${rowStatus(o.status)}</td><td>${!demo ? `<a class="link-button" href="/api/orders/${o.id}/pick-list.csv">Pick list CSV</a> ` : ''}${!demo && o.status === 'reserved' && !outboundPicks.some(p => p.order_id === o.id && p.status !== 'canceled') ? `<button class="link-button" data-order="${o.id}" data-action="fulfill">Fulfill</button> <button class="link-button muted-link" data-order="${o.id}" data-action="cancel">Cancel</button>` : '—'}</td></tr>`));
      byId('movements-table').innerHTML = table(['Time', 'Product', 'Location', 'Action', 'On hand Δ', 'Reserved Δ'], movementRows.map(m =>
        `<tr><td>${safe(m.created_at.slice(0, 16).replace('T', ' '))}</td><td>${safe(m.sku)}</td><td>${safe(m.warehouse)}</td><td>${safe(m.kind)}</td><td>${m.on_hand_delta > 0 ? '+' : ''}${m.on_hand_delta}</td><td>${m.reserved_delta > 0 ? '+' : ''}${m.reserved_delta}</td></tr>`));
      byId('suppliers-table').innerHTML = table(['Supplier', 'Contact'], supplierRows.map(s =>
        `<tr><td><strong>${safe(s.name)}</strong></td><td>${safe(s.email || 'No contact provided')}</td></tr>`));
      byId('purchases-table').innerHTML = table(['Reference', 'Supplier', 'Warehouse', 'Items', 'Expected', 'Status', 'Action'], purchaseRows.map(po =>
        `<tr><td><strong>${safe(po.reference)}</strong></td><td>${safe(po.supplier)}</td><td>${safe(po.warehouse)}</td><td>${po.items.map(item =>
           `${safe(item.sku)}: ${item.received}/${item.ordered} received${!demo && item.outstanding > 0 && ['ordered', 'partial'].includes(po.status)
             ? ` <button class="link-button" data-purchase-receive="${po.id}" data-line="${item.line_id}" data-outstanding="${item.outstanding}">Receive</button>` : ''}`).join('<br>')}</td><td>${safe(po.expected_date || '—')}</td><td>${rowStatus(po.status)}</td><td>${!demo && ['ordered', 'partial'].includes(po.status)
          ? `<button class="link-button muted-link" data-purchase-cancel="${po.id}">Cancel</button>` : '—'}</td></tr>`));
      byId('outgoing-queue').innerHTML = table(['Order','Customer','Due','Status'], planning.outgoing_orders.map(o =>
        `<tr><td>#${o.id}</td><td>${safe(o.customer)}</td><td>${safe(o.due_date)}</td><td>${o.overdue ? '<span class="status status-low">Overdue</span>' : 'Scheduled'}</td></tr>`));
      byId('incoming-queue').innerHTML = table(['PO','Expected','Status'], planning.incoming_purchases.map(o =>
        `<tr><td>${safe(o.reference)}</td><td>${safe(o.expected_date || 'Not scheduled')}</td><td>${o.overdue ? '<span class="status status-low">Overdue</span>' : safe(o.status)}</td></tr>`));
      byId('transfers-table').innerHTML = table(['Transfer ID', 'SKU', 'From', 'To', 'Units', 'When'], transfers.map(t =>
        `<tr><td>#${t.id}</td><td>${safe(t.sku)}</td><td>${safe(t.source)}</td><td>${safe(t.destination)}</td><td>${t.quantity}</td><td>${safe(t.created_at.slice(0, 16))}</td></tr>`));
      byId('counts-table').innerHTML = table(['SKU', 'Warehouse', 'Expected', 'Counted', 'Status', 'Action'], counts.map(c =>
        `<tr><td>${safe(c.sku)}</td><td>${safe(c.warehouse)}</td><td>${c.expected_on_hand}</td><td>${c.counted_on_hand === null ? '—' : c.counted_on_hand}</td><td>${rowStatus(c.status)}</td><td>${!demo && role === 'owner' && c.status === 'open' ? `<button class="link-button" data-count-post="${c.id}">Reconcile</button> <button class="link-button muted-link" data-count-cancel="${c.id}">Cancel</button>` : '—'}</td></tr>`));
      byId('bin-counts-table').innerHTML = table(['Warehouse', 'Bin', 'SKU', 'Expected', 'Counted', 'Variance', 'Status', 'Action'],
        binCounts.map(c => `<tr><td>${safe(c.warehouse)}</td><td><strong>${safe(c.bin_code)}</strong></td><td>${safe(c.sku)}</td><td>${c.expected_on_hand}</td><td>${c.counted_on_hand === null ? '—' : c.counted_on_hand}</td><td>${c.variance === null ? '—' : c.variance > 0 ? '+' + c.variance : c.variance}</td><td>${rowStatus(c.status)}</td><td>${!demo && role === 'owner' && c.status === 'open' ? `<button class="link-button" data-bin-count-post="${c.id}" data-expected="${c.expected_on_hand}" data-bin-code="${safe(c.bin_code)}">Reconcile</button> <button class="link-button muted-link" data-bin-count-cancel="${c.id}">Cancel</button>` : '—'}</td></tr>`));
      byId('returns-table').innerHTML = table(['Reference', 'Order', 'SKU', 'Units', 'When'], returns.map(r =>
        `<tr><td>${safe(r.reference)}</td><td>#${r.order_id}</td><td>${safe(r.sku)}</td><td>${r.quantity}</td><td>${safe(r.created_at.slice(0, 16))}</td></tr>`));
      byId('replenishment-table').innerHTML = table(['Product', 'Location', 'Available', 'Open PO units', 'Suggested'], replenishment.map(r =>
        `<tr><td><strong>${safe(r.product)}</strong><small>${safe(r.sku)}</small></td><td>${safe(r.warehouse)}</td><td>${r.available}</td><td>${r.incoming}</td><td><strong>${r.suggested_quantity}</strong></td></tr>`));
      if (byId('staff-table')) byId('staff-table').innerHTML = table(['Email', 'Role', 'Action'], team.map(u =>
        `<tr><td>${safe(u.email)}</td><td>${rowStatus(u.role)}</td><td>${u.role === 'owner' ? '—' : `<button class="link-button" data-staff-id="${u.id}" data-role="${safe(u.role)}">Change role</button>`}</td></tr>`));
      // Warehouse execution: putaway and relocations are movement of PLACEMENT,
      // not additional stock receipts or stock accounting debits.
      const metrics = {
        'stat-bins': locations.length,
        'stat-placed': reconciliation.reduce((sum, r) => sum + r.placed, 0),
        'stat-unlocated': reconciliation.reduce((sum, r) => sum + r.unlocated, 0),
        'stat-pending-putaway': reconciliation.reduce((sum, r) => sum + r.pending_putaway, 0),
        'stat-task-queued': tasks.filter(t => t.status === 'queued').length,
        'stat-task-assigned': tasks.filter(t => t.status === 'assigned').length,
        'stat-task-progress': tasks.filter(t => t.status === 'in_progress').length,
        'stat-task-completed': tasks.filter(t => t.status === 'completed').length
      };
      for (const [id, value] of Object.entries(metrics)) if (byId(id)) byId(id).textContent = value.toLocaleString();
      byId('bin-table').innerHTML = table(['Warehouse','Bin code','Zone / Aisle','Rack / Shelf','Placed units','Capacity'],
        locations.map(b => `<tr><td>${safe(b.warehouse)}</td><td><strong>${safe(b.code)}</strong></td><td>${safe(b.zone || '—')} / ${safe(b.aisle || '—')}</td><td>${safe(b.rack || '—')} / ${safe(b.shelf || '—')}</td><td>${b.placed_units}</td><td>${b.capacity_units ?? '—'}</td></tr>`));
      byId('bin-stock-table').innerHTML = table(['Warehouse bin','SKU','Placed','Allocated to moves','Free in bin'],
        placedStock.map(b => `<tr><td>${safe(b.bin_code)}</td><td><strong>${safe(b.sku)}</strong></td><td>${b.on_hand}</td><td>${b.committed_to_moves}</td><td>${b.available}</td></tr>`));
      byId('unlocated-table').innerHTML = table(['Warehouse','SKU','On hand','In bins','Unlocated','Putaway pending','Order staged','Free unlocated'],
        reconciliation.map(r => `<tr><td>${safe(r.warehouse)}</td><td>${safe(r.sku)}</td><td>${r.on_hand}</td><td>${r.placed}</td><td>${r.unlocated}</td><td>${r.pending_putaway}</td><td>${r.staged_outbound ?? 0}</td><td>${r.free_unlocated ?? r.unlocated}</td></tr>`));
      byId('tasks-table').innerHTML = table(['Priority','Task','SKU / quantity','Source → target','Assigned to','Status','Actions'],
        tasks.map(t => {
          const active = ['queued','assigned','in_progress'].includes(t.status);
          const owned = currentUser && currentUser === t.assigned_user_id;
          const controls = demo ? '—' : `<span class="task-actions">
            ${t.status === 'queued' ? `<button class="link-button" data-task-action="claim" data-task-id="${t.id}">Claim</button>` : ''}
            ${t.status === 'assigned' && owned ? `<button class="link-button" data-task-action="start" data-task-id="${t.id}">Start</button>` : ''}
            ${t.status === 'in_progress' && owned ? `<button class="link-button" data-task-action="scan" data-task-id="${t.id}">Scan</button>` : ''}
            ${canManageWork && ['queued','assigned'].includes(t.status) ? `<button class="link-button" data-task-action="assign" data-task-id="${t.id}">Assign</button>` : ''}
            ${canManageWork && active ? `<button class="link-button muted-link" data-task-action="cancel" data-task-id="${t.id}">Cancel</button>` : ''}
            <button class="link-button muted-link" data-task-action="history" data-task-id="${t.id}">History</button>
            </span>`;
          return `<tr><td>P${t.priority}</td><td><strong>#${t.id}</strong><small>${safe(t.kind)}</small></td><td>${safe(t.sku)} × ${t.quantity}</td><td>${safe(t.from_bin || 'UNLOCATED')} → ${safe(t.to_bin)}</td><td>${t.assigned_user_id ?? 'Unassigned'}</td><td>${rowStatus(t.status)}</td><td>${controls}</td></tr>`;
        }));
      document.querySelectorAll('.fulfilled-order-select').forEach(select => {
        select.innerHTML = orderRows.filter(o => o.status === 'fulfilled').map(o =>
          `<option value="${o.id}">#${o.id} · ${safe(o.customer_name)}</option>`).join('');
      });
      document.querySelectorAll('.supplier-select').forEach(select => {
        const old = select.value;
        select.innerHTML = supplierRows.map(s => `<option value="${s.id}">${safe(s.name)}</option>`).join('');
        if (supplierRows.some(s => String(s.id) === old)) select.value = old;
      });
      document.querySelectorAll('.warehouse-select').forEach(select => {
        const old = select.value;
        select.innerHTML = warehouses.map(w => `<option value="${w.id}">${safe(w.name)}</option>`).join('');
        if (warehouses.some(w => String(w.id) === old)) select.value = old;
      });
      document.querySelectorAll('.sku-select').forEach(select => {
        const old = select.value;
        select.innerHTML = products.map(p => `<option value="${safe(p.sku)}">${safe(p.name)} · ${safe(p.sku)}</option>`).join('');
        if (products.some(p => p.sku === old)) select.value = old;
      });
      refreshTaskBinOptions();
      refreshBinCountOptions();
      renderOutbound();
      if (!demo) await refreshOutboundOptions();
    } catch (error) { notice(error.message, true); }
  }
  async function submit(id, path, build) {
    const form = byId(id); if (!form) return;
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const data = new FormData(form);
      try {
        await api(path, {method: 'POST', body: JSON.stringify(build(data))});
        notice('Saved successfully. Your warehouse records are updated.');
        form.reset(); await load();
      } catch (error) { notice(error.message, true); }
    });
  }
  document.querySelectorAll('[data-section]').forEach(button => button.addEventListener('click', () => {
    document.querySelectorAll('[data-section]').forEach(b => b.classList.toggle('active', b === button));
    document.querySelectorAll('[data-view]').forEach(el => el.classList.toggle('hidden', el.dataset.view !== button.dataset.section));
  }));
  if (!demo) {
    submit('product-form', '/products', d => ({sku: d.get('sku'), name: d.get('name'),
      price_cents: Math.round(Number(d.get('price')) * 100), reorder_point: Number(d.get('reorder_point'))}));
    submit('receive-form', '/stock/receive', d => ({warehouse_id: Number(d.get('warehouse_id')), sku: d.get('sku'),
      quantity: Number(d.get('quantity')), note: d.get('note')}));
    submit('warehouse-form', '/warehouses', d => ({name: d.get('name'), city: d.get('city')}));
    submit('supplier-form', '/suppliers', d => ({name: d.get('name'), email: d.get('email')}));
    submit('purchase-form', '/purchase-orders', d => ({reference: d.get('reference'),
      supplier_id: Number(d.get('supplier_id')), warehouse_id: Number(d.get('warehouse_id')),
      expected_date: d.get('expected_date') || null,
      items: [{sku: d.get('sku'), quantity: Number(d.get('quantity'))}]}));
    // Keep the same key if the network fails and the operator retries unchanged data.
    // Generate a new key only for a new or edited operation, never per HTTP attempt.
    const transferForm = byId('transfer-form');
    let pendingTransfer = null;
    if (transferForm) transferForm.addEventListener('submit', async event => {
      event.preventDefault();
      const d = new FormData(transferForm);
      const payload = {
        source_warehouse_id: Number(d.get('source_warehouse_id')),
        destination_warehouse_id: Number(d.get('destination_warehouse_id')),
        sku: d.get('sku'), quantity: Number(d.get('quantity')), note: d.get('note')
      };
      const serialized = JSON.stringify(payload);
      if (!pendingTransfer || pendingTransfer.serialized !== serialized) {
        pendingTransfer = {serialized, key: crypto.randomUUID()};
      }
      const submitButton = transferForm.querySelector('button[type="submit"]');
      submitButton.disabled = true;
      try {
        const result = await api('/transfers', {
          method: 'POST', body: serialized,
          headers: {'Idempotency-Key': pendingTransfer.key}
        });
        pendingTransfer = null;
        notice(`Transfer #${result.id} ${result.replayed ? 'already completed; no stock moved again.' : 'completed.'}`);
        transferForm.reset();
        await load();
      } catch (error) {
        // Do not discard the key: a timeout might follow a successful commit.
        notice(error.message + ' Retrying unchanged details is safe.', true);
      } finally {
        submitButton.disabled = false;
      }
    });
    submit('count-form', '/cycle-counts', d => ({warehouse_id: Number(d.get('warehouse_id')),
      sku: d.get('sku'), note: d.get('note')}));
    submit('bin-count-form', '/bin-cycle-counts', d => ({
      warehouse_id: Number(d.get('warehouse_id')), bin_id: Number(d.get('bin_id')),
      sku: d.get('sku'), note: d.get('note') || ''
    }));
    if (byId('bin-count-form')) byId('bin-count-form').elements.warehouse_id.addEventListener(
      'change', refreshBinCountOptions);
    submit('return-form', '/returns', d => ({order_id: Number(d.get('order_id')),
      sku: d.get('sku'), quantity: Number(d.get('quantity')),
      reference: d.get('reference'), reason: d.get('reason')}));
    submit('order-form', '/orders', d => ({warehouse_id: Number(d.get('warehouse_id')),
      customer_name: d.get('customer_name'), due_date: d.get('due_date'),
      items: [{sku: d.get('sku'), quantity: Number(d.get('quantity'))}]}));
    const today = new Date();
    const localToday = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
    if (byId('due-date')) {byId('due-date').value = localToday; byId('due-date').min = localToday;}
    const importForm = byId('import-form');
    if (importForm) importForm.addEventListener('submit', async event => {
      event.preventDefault();
      try {
        const result = await api('/import/products', {method: 'POST', body: new FormData(importForm)});
        notice(`Imported ${result.created} products (${result.skipped} existing or repeated SKUs skipped).`);
        importForm.reset(); await load();
      } catch (error) { notice(error.message, true); }
    });
    byId('counts-table').addEventListener('click', async event => {
      const post = event.target.closest('[data-count-post]');
      const cancel = event.target.closest('[data-count-cancel]');
      if (!post && !cancel) return;
      try {
        if (post) {
          const answer = window.prompt('Enter the physically counted units (whole number):');
          if (answer === null) return;
          const quantity = Number(answer);
          if (!Number.isInteger(quantity) || quantity < 0) return notice('Count must be a nonnegative whole number.', true);
          if (!window.confirm(`Post cycle count #${post.dataset.countPost}? This adjusts inventory.`)) return;
          await api(`/cycle-counts/${post.dataset.countPost}/post`, {method:'POST',
            body:JSON.stringify({counted_on_hand:quantity})});
        } else {
          if (!window.confirm('Cancel this physical count?')) return;
          await api(`/cycle-counts/${cancel.dataset.countCancel}/cancel`, {method:'POST'});
        }
        notice('Cycle count updated.'); await load();
      } catch (error) { notice(error.message, true); }
    });
    byId('bin-counts-table').addEventListener('click', async event => {
      const post = event.target.closest('[data-bin-count-post]');
      const cancel = event.target.closest('[data-bin-count-cancel]');
      if (!post && !cancel) return;
      try {
        if (post) {
          const answer = window.prompt(`Physical units counted for bin ${post.dataset.binCode} (expected ${post.dataset.expected}):`);
          if (answer === null) return;
          if (!/^\d+$/.test(answer.trim())) return notice('Enter a nonnegative whole number.', true);
          const counted = Number(answer.trim());
          if (!Number.isSafeInteger(counted) || counted > 10000000) return notice('Count must be between 0 and 10,000,000.', true);
          const variance = counted - Number(post.dataset.expected);
          if (!window.confirm(`Reconcile bin count #${post.dataset.binCountPost} with ${counted} units (variance ${variance >= 0 ? '+' : ''}${variance})? This updates the warehouse accounting balance.`)) return;
          await api(`/bin-cycle-counts/${post.dataset.binCountPost}/post`, {
            method:'POST', body:JSON.stringify({counted_on_hand:counted})});
          notice('Bin count posted; bin and aggregate inventory reconciled.');
        } else {
          if (!window.confirm('Cancel this bin-specific physical count?')) return;
          await api(`/bin-cycle-counts/${cancel.dataset.binCountCancel}/cancel`, {method:'POST'});
          notice('Bin count canceled.');
        }
        await load();
      } catch (error) { notice(error.message, true); }
    });
    const inviteForm = byId('invite-form');
    if (inviteForm) inviteForm.addEventListener('submit', async event => {
      event.preventDefault(); const data = new FormData(inviteForm);
      try {
        const invited = await api('/staff/invitations', {method:'POST', body:JSON.stringify({
          email:data.get('email'), role:data.get('role')})});
        const workspace = document.querySelector('.slug-code')?.textContent.trim() || '';
        const link = `${location.origin}/join#token=${encodeURIComponent(invited.token)}&workspace=${encodeURIComponent(workspace)}`;
        byId('invite-output').textContent = `Share securely (shown once): ${link}`;
        notice('Invitation created. Copy the one-time link below the invitation form.');
        inviteForm.reset(); await load();
      } catch(error) { notice(error.message,true); }
    });
    const staffTable = byId('staff-table');
    if (staffTable) staffTable.addEventListener('click', async event => {
      const btn=event.target.closest('[data-staff-id]'); if (!btn) return;
      const desired=window.prompt('New role: manager, staff, or disabled',btn.dataset.role);
      if (desired === null) return;
      if (!['manager','staff','disabled'].includes(desired)) return notice('Choose manager, staff, or disabled.',true);
      if (!window.confirm(`Set employee #${btn.dataset.staffId} to ${desired}?`)) return;
      try { await api(`/staff/${btn.dataset.staffId}/role`,{method:'PATCH',
        body:JSON.stringify({role:desired})}); notice('Team member updated.'); await load(); }
      catch(error) { notice(error.message,true); }
    });
    byId('purchases-table').addEventListener('click', async event => {
      const receive = event.target.closest('[data-purchase-receive]');
      const cancel = event.target.closest('[data-purchase-cancel]');
      if (!receive && !cancel) return;
      try {
        if (receive) {
          const max = Number(receive.dataset.outstanding);
          const answer = window.prompt(`How many units arrived? Outstanding: ${max}`, String(max));
          if (answer === null) return;
          const quantity = Number(answer);
          if (!Number.isInteger(quantity) || quantity < 1 || quantity > max) {
            return notice(`Enter a whole number between 1 and ${max}.`, true);
          }
          await api(`/purchase-orders/${receive.dataset.purchaseReceive}/receive`, {
            method: 'POST', body: JSON.stringify({line_id: Number(receive.dataset.line), quantity})});
          notice('Receipt saved and stock history updated.');
        } else {
          if (!window.confirm(`Cancel outstanding units on purchase order #${cancel.dataset.purchaseCancel}?`)) return;
          await api(`/purchase-orders/${cancel.dataset.purchaseCancel}/cancel`, {method: 'POST'});
          notice('Purchase order cancelled. Previously received stock remains in inventory.');
        }
        await load();
      } catch (error) { notice(error.message, true); }
    });
    if (byId('bin-form')) submit('bin-form', '/locations', d => ({
      warehouse_id:Number(d.get('warehouse_id')), code:d.get('code'),
      zone:d.get('zone'), aisle:d.get('aisle'), rack:d.get('rack'), shelf:d.get('shelf'),
      capacity_units:d.get('capacity_units') ? Number(d.get('capacity_units')) : null
    }));
    if (byId('task-form')) {
      const taskForm = byId('task-form');
      let pendingWork = null;
      taskForm.elements.kind.addEventListener('change', refreshTaskBinOptions);
      taskForm.elements.warehouse_id.addEventListener('change', refreshTaskBinOptions);
      taskForm.addEventListener('submit', async event => {
        event.preventDefault();
        const d = new FormData(taskForm);
        const body = JSON.stringify({
          kind:d.get('kind'), warehouse_id:Number(d.get('warehouse_id')),
          sku:d.get('sku'), quantity:Number(d.get('quantity')),
          from_bin_id:d.get('from_bin_id') ? Number(d.get('from_bin_id')) : null,
          to_bin_id:d.get('to_bin_id') ? Number(d.get('to_bin_id')) : null,
          priority:Number(d.get('priority')), note:d.get('note') || ''
        });
        if (!pendingWork || pendingWork.body !== body)
          pendingWork = {body, key:crypto.randomUUID()};
        const button=taskForm.querySelector('button[type="submit"]'); button.disabled=true;
        try {
          const saved=await api('/tasks',{method:'POST',body,
            headers:{'Idempotency-Key':pendingWork.key}});
          pendingWork=null;
          notice(`Task #${saved.id} ${saved.replayed ? 'already registered' : 'created in work queue'}.`);
          taskForm.reset(); await load();
        } catch(error) {
          notice(`${error.message}. Keep unchanged details if retrying after a connection failure.`,true);
        } finally {button.disabled=false;}
      });
    }
    const taskScanForm = byId('task-scan-form');
    if (taskScanForm) taskScanForm.addEventListener('submit',async event => {
      event.preventDefault();
      const d=new FormData(taskScanForm);
      try {
        const result=await api(`/tasks/${Number(d.get('task_id'))}/complete`,{
          method:'POST',body:JSON.stringify({scan_sku:d.get('scan_sku'),
            scan_to_bin:d.get('scan_to_bin'), scan_from_bin:d.get('scan_from_bin') || null})});
        notice(`Task #${result.id} ${result.replayed ? 'already confirmed' : 'verified and completed'}.`);
        taskScanForm.reset(); await load();
      } catch(error) {notice(error.message,true);}
    });
    byId('tasks-table').addEventListener('click',async event => {
      const button=event.target.closest('[data-task-action]'); if (!button) return;
      const id=Number(button.dataset.taskId), action=button.dataset.taskAction;
      try {
        if (action === 'scan') {
          const t=workTasks.find(t=>t.id===id);
          if (!taskScanForm || !t) return;
          taskScanForm.elements.task_id.value=id;
          taskScanForm.elements.scan_sku.value='';
          taskScanForm.elements.scan_from_bin.value='';
          taskScanForm.elements.scan_to_bin.value='';
          taskScanForm.scrollIntoView({behavior:'smooth',block:'center'});
          taskScanForm.elements.scan_sku.focus();
          return;
        }
        if (action === 'history') {
          const events=await api(`/tasks/${id}/events`);
          window.alert(events.map(e=>`${e.created_at.slice(0,16)} · ${e.action} · operator #${e.actor_id}${e.detail ? ' · '+e.detail : ''}`).join('\n') || 'No events');
          return;
        }
        if (action === 'cancel' && !window.confirm(`Cancel task #${id} and release reservations?`)) return;
        let body;
        if (action === 'assign') {
          const choices=assignees.map(u=>`${u.id}: ${u.email} (${u.role})`).join('\n');
          const answer=window.prompt(`Assign task #${id} to an employee ID. Leave blank to unassign.\n${choices}`);
          if (answer===null) return;
          if (answer.trim() && (!Number.isInteger(Number(answer)) || Number(answer)<1))
            return notice('Enter a valid employee ID.',true);
          body=JSON.stringify({assigned_user_id:answer.trim()?Number(answer):null});
        }
        await api(`/tasks/${id}/${action}`,{method:'POST',...(body?{body}:{})});
        notice(`Task #${id} updated.`); await load();
      } catch(error) {notice(error.message,true);}
    });

    if (byId('out-plan-order')) {
      byId('out-plan-order').addEventListener('change', () => refreshOutboundLines().catch(e => notice(e.message,true)));
      byId('out-plan-line').addEventListener('change', refreshOutboundBins);
    }
    let pendingPlan = null;
    const planForm = byId('out-plan-form');
    if (planForm) planForm.addEventListener('submit', async event => {
      event.preventDefault();
      const d = new FormData(planForm), orderId = Number(d.get('order_id'));
      const body = JSON.stringify({order_line_id: Number(d.get('order_line_id')),
        bin_id: Number(d.get('bin_id')), quantity: Number(d.get('quantity'))});
      const serialized = `${orderId}:${body}`;
      if (!pendingPlan || pendingPlan.serialized !== serialized)
        pendingPlan = {serialized, key: crypto.randomUUID()};
      const button = planForm.querySelector('button[type="submit"]'); button.disabled = true;
      try {
        const result = await api(`/outbound/orders/${orderId}/picks`,{method:'POST',body,
          headers:{'Idempotency-Key':pendingPlan.key}});
        pendingPlan = null;
        notice(`Order-bound pick #${result.id} ${result.replayed ? 'already registered' : 'allocated from the bin'}.`);
        await load();
      } catch(e) {notice(e.message + ' Unchanged retries remain safe.',true);}
      finally {button.disabled = false;}
    });
    const scanForm = byId('out-scan-form');
    if (scanForm) scanForm.addEventListener('submit',async event => {
      event.preventDefault();
      const d=new FormData(scanForm), pickId=Number(d.get('pick_id'));
      try {
        const result=await api(`/outbound/picks/${pickId}/scan`,{method:'POST',
          body:JSON.stringify({scan_sku:d.get('scan_sku'),scan_bin:d.get('scan_bin')})});
        notice(`Pick #${result.id} ${result.replayed ? 'was already verified' : 'scanned to outbound staging'}.`);
        scanForm.reset(); await load();
      } catch(e) {notice(e.message,true);}
    });
    const picksTable=byId('out-picks-table');
    if (picksTable) picksTable.addEventListener('click',async event => {
      const button=event.target.closest('[data-out-action]'); if (!button) return;
      const pickId=Number(button.dataset.outPick), action=button.dataset.outAction;
      const pick=outboundPicks.find(p=>p.id===pickId);
      if (!pick) return;
      if (action==='scan') {
        scanForm.elements.pick_id.value=pick.id;
        scanForm.elements.scan_sku.value=''; scanForm.elements.scan_bin.value='';
        scanForm.scrollIntoView({behavior:'smooth',block:'center'});
        scanForm.elements.scan_sku.focus(); return;
      }
      if (action==='pack') {
        const f=byId('out-pack-form'); f.elements.pick_id.value=pick.id;
        f.elements.scan_sku.value=''; f.scrollIntoView({behavior:'smooth',block:'center'});
        f.elements.scan_sku.focus(); return;
      }
      try {
        if (action==='events') {
          const events=await api(`/outbound/picks/${pickId}/events`);
          window.alert(events.map(e=>`${e.created_at.slice(0,16)} · ${e.action} · worker #${e.actor_id} · ${e.detail}`).join('\n') || 'No events'); return;
        }
        if (action==='cancel' && !window.confirm(`Cancel pick #${pickId} and release reserved bin units?`)) return;
        await api(`/outbound/picks/${pickId}/${action}`,{method:'POST'});
        notice(`Outbound pick #${pickId} updated.`); await load();
      } catch(e) { notice(e.message,true); }
    });

    const cartonForm=byId('out-carton-form');
    if (cartonForm) cartonForm.addEventListener('submit',async event => {
      event.preventDefault(); const d=new FormData(cartonForm);
      try {
        const result=await api(`/outbound/orders/${Number(d.get('order_id'))}/cartons`,
          {method:'POST',body:JSON.stringify({code:d.get('code')})});
        notice(`Carton ${result.code} created.`); cartonForm.reset(); await load();
      } catch(e) {notice(e.message,true);}
    });
    const packForm=byId('out-pack-form');
    if (packForm) packForm.addEventListener('submit',async event => {
      event.preventDefault(); const d=new FormData(packForm);
      try {
        const result=await api(`/outbound/cartons/${Number(d.get('carton_id'))}/pack`,
          {method:'POST',body:JSON.stringify({pick_id:Number(d.get('pick_id')),
            scan_sku:d.get('scan_sku'),scan_carton:d.get('scan_carton')})});
        notice(`Pick #${result.pick_id} verified in carton.`); packForm.reset(); await load();
      } catch(e) {notice(e.message,true);}
    });
    const cartonTable=byId('out-cartons-table');
    if (cartonTable) cartonTable.addEventListener('click',async event => {
      const button=event.target.closest('[data-out-carton-action]'); if (!button) return;
      const id=Number(button.dataset.outCarton), action=button.dataset.outCartonAction;
      const carton=outboundCartons.find(c=>c.id===id);
      if (!carton) return;
      if (action==='select') {
        packForm.elements.carton_id.value=carton.id;
        packForm.elements.scan_carton.value='';
        packForm.scrollIntoView({behavior:'smooth',block:'center'});
        packForm.elements.scan_carton.focus(); return;
      }
      if (!window.confirm(`Seal carton ${carton.code}? Packing will be locked.`)) return;
      try {
        await api(`/outbound/cartons/${id}/seal`,{method:'POST'});
        notice(`Carton ${carton.code} sealed.`); await load();
      } catch(e) {notice(e.message,true);}
    });
    let pendingShipment=null;
    const dispatchForm=byId('out-dispatch-form');
    if (dispatchForm) dispatchForm.addEventListener('submit',async event => {
      event.preventDefault(); const d=new FormData(dispatchForm);
      const orderId=Number(d.get('order_id'));
      const body=JSON.stringify({carrier:d.get('carrier'),tracking_reference:d.get('tracking_reference')});
      const serialized=`${orderId}:${body}`;
      if (!pendingShipment || pendingShipment.serialized!==serialized)
        pendingShipment={serialized,key:crypto.randomUUID()};
      if (!window.confirm(`Post final warehouse goods issue for order #${orderId}?`)) return;
      const button=dispatchForm.querySelector('button[type="submit"]'); button.disabled=true;
      try {
        const result=await api(`/outbound/orders/${orderId}/dispatch`,{method:'POST',body,
          headers:{'Idempotency-Key':pendingShipment.key}});
        pendingShipment=null;
        notice(`Shipment #${result.id} ${result.replayed ? 'already confirmed' : 'dispatched; stock deducted'}.`);
        dispatchForm.reset(); await load();
      } catch(e) {notice(e.message + ' Retry unchanged details to avoid duplicate posting.',true);}
      finally {button.disabled=false;}
    });

    byId('orders-table').addEventListener('click', async event => {
      const button = event.target.closest('[data-order]'); if (!button) return;
      if (!window.confirm(`Confirm: ${button.dataset.action} order #${button.dataset.order}?`)) return;
      try {
        await api(`/orders/${button.dataset.order}/${button.dataset.action}`, {method:'POST'});
        notice('Order updated and stock ledger reconciled.'); await load();
      } catch (error) { notice(error.message, true); }
    });
  }
  load();
})();
