(() => {
  const form=document.getElementById('join-form'); if (!form) return;
  const args=new URLSearchParams(location.hash.slice(1));
  const token=args.get('token') || '';
  document.getElementById('join-workspace').value=args.get('workspace') || '';
  const status=document.getElementById('join-message');
  if (!token) { status.textContent='Invitation token missing. Ask your manager for a new link.'; return; }
  form.addEventListener('submit',async event => {
    event.preventDefault();
    const password=new FormData(form).get('password');
    try {
      const r=await fetch('/api/staff/invitations/accept',{method:'POST',
        headers:{'Content-Type':'application/json'},body:JSON.stringify({token,password})});
      const data=await r.json();
      if (!r.ok) throw new Error(data.error || 'Could not accept invitation.');
      status.textContent=`Account created for ${data.email}. Sign in using your workspace ID.`;
      form.reset();
      history.replaceState(null,'','/join');
    } catch(error) { status.textContent=error.message; }
  });
})();
