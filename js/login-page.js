const SESSION_KEY='cadena_custodia_sesion';
let loginTurnstileToken=null, loginTurnstileWidget=null;
document.addEventListener('DOMContentLoaded',()=>{
  if(window.lucide) lucide.createIcons();
  const saved=localStorage.getItem('cadena_custodia_theme')||'dark';
  document.body.classList.toggle('theme-light',saved==='light');
  document.body.classList.toggle('theme-dark',saved!=='light');
  if(sessionStorage.getItem(SESSION_KEY)){location.replace('index.html');return;}
  const form=document.getElementById('loginForm'),err=document.getElementById('loginError'),btn=form.querySelector('button');
  const widget=document.getElementById('turnstileWidget');
  const initCaptcha=()=>{
    if(TURNSTILE_SITE_KEY==='PON_AQUI_TU_TURNSTILE_SITE_KEY'){
      widget.innerHTML='<small>Captcha sin configurar: disponible únicamente en entorno de desarrollo.</small>';
      loginTurnstileToken='dev-local'; return;
    }
    if(!window.turnstile){setTimeout(initCaptcha,200);return;}
    loginTurnstileWidget=window.turnstile.render(widget,{sitekey:TURNSTILE_SITE_KEY,callback:t=>loginTurnstileToken=t,'expired-callback':()=>loginTurnstileToken=null,'error-callback':()=>loginTurnstileToken=null});
  };
  initCaptcha();
  form.addEventListener('submit',async e=>{
    e.preventDefault();err.textContent='';
    if(!loginTurnstileToken){err.textContent='Completa la verificación de seguridad.';return;}
    btn.disabled=true;btn.textContent='Validando…';
    try{
      const res=await fetch(`${API_BASE_URL}/api/login`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({usuario:document.getElementById('loginUsuario').value.trim(),password:document.getElementById('loginPassword').value,turnstileToken:loginTurnstileToken})});
      const data=await res.json();if(!res.ok)throw new Error(data.error||'No fue posible iniciar sesión.');
      sessionStorage.setItem(SESSION_KEY,JSON.stringify({token:data.token,user:data.user}));location.replace('index.html');
    }catch(error){err.textContent=error.message||'No se pudo conectar con el servidor.';if(window.turnstile&&loginTurnstileWidget!==null){window.turnstile.reset(loginTurnstileWidget);loginTurnstileToken=null;}}
    finally{btn.disabled=false;btn.innerHTML='Iniciar sesión <span>→</span>'}
  });
});
