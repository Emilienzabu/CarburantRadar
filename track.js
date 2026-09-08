(function(){
  try{
    var uid=localStorage.getItem('cr_uid');
    if(!uid){uid='u'+Date.now().toString(36)+Math.random().toString(36).slice(2,12);localStorage.setItem('cr_uid',uid);}
    var pays=null;
    if(location.pathname.indexOf('/france/')!==-1)pays='france';
    else if(location.pathname.indexOf('/espagne/')!==-1)pays='espagne';
    else if(location.pathname.indexOf('/italie/')!==-1)pays='italie';
    fetch('https://carburant-proxy.emilienzabukovec09.workers.dev/track',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uid:uid,pays:pays})}).catch(function(){});
  }catch(e){}
})();
