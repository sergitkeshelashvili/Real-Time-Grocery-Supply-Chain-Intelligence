const fmt = n => Number(n || 0).toLocaleString();
function example(q) { document.querySelector('#prompt').value = q; askCopilot(); }
document.addEventListener('DOMContentLoaded', () => {
  document.querySelector('#prompt').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); askCopilot(); }
  });
});

async function askCopilot() {
  const prompt = document.querySelector('#prompt').value.trim();
  const btn = document.querySelector('#ask');
  const state = document.querySelector('#promptState');
  const out = document.querySelector('#promptAnswer');
  if (!prompt) { state.textContent = 'Enter a question first.'; return; }
  btn.disabled = true; state.textContent = 'Checking live supply-chain and weather data…'; out.hidden = true;
  try {
    const response = await fetch('/analyze', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({prompt}) });
    const data = await response.json();
    if (!response.ok) throw Error(data.detail || 'Request failed');
    out.textContent = data.answer; out.hidden = false;
    state.textContent = `Live ClickHouse data · ${data.provider} · ${new Date(data.generated_at).toLocaleString()}`;
  } catch (error) { state.textContent = `Could not analyze prompt: ${error.message}`; }
  finally { btn.disabled = false; }
}

function drawDemandTrend(points) {
  const svg = document.querySelector('#demandChart');
  const empty = document.querySelector('#demandEmpty');
  const vals = points.map(p => p.quantity);
  if (!vals.some(v => v > 0)) { svg.innerHTML = ''; empty.hidden = false; return; }
  empty.hidden = true;
  const observedMax = Math.max(...vals, 1);
  const max = Math.max(100000, Math.ceil(observedMax/100000)*100000);
  const left = 34, right = 790, top = 14, bottom = 176;
  const coords = vals.map((v,i) => [left + i*(right-left)/(vals.length-1), bottom - v/max*(bottom-top)]);
  const line = coords.map(([x,y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const area = `${left},${bottom} ${line} ${right},${bottom}`;
  const grid = [0,.5,1].map(frac => { const y=bottom-frac*(bottom-top); return `<line x1="${left}" x2="${right}" y1="${y}" y2="${y}" class="gridline"/><text x="2" y="${y+4}" class="axislabel">${Math.round(max*frac)}</text>`; }).join('');
  const last=coords.at(-1), current=vals.at(-1);
  svg.innerHTML = `<defs><linearGradient id="demandFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#57e0bb" stop-opacity=".32"/><stop offset="100%" stop-color="#57e0bb" stop-opacity="0"/></linearGradient></defs>${grid}<polygon points="${area}" fill="url(#demandFill)"/><polyline points="${line}" class="demandline"/><circle cx="${last[0]}" cy="${last[1]}" r="5" class="latestdot"><title>Current hour: ${current.toFixed(1)} units</title></circle><text x="${left}" y="207" class="axislabel">7 days ago</text><text x="${right-55}" y="207" class="axislabel">now · ${current.toFixed(1)} units</text>`;
}

function renderWeather(items) {
  const el=document.querySelector('#weather'); el.replaceChildren();
  if (!items.length) { el.textContent='No live weather received yet. Check the OpenWeather key and wait for the next poll.'; return; }
  for (const w of items) {
    const card=document.createElement('article'); card.className='weather-card';
    const symbol=/rain|drizzle|thunder/i.test(w.condition)?'🌧':/snow/i.test(w.condition)?'❄️':/cloud/i.test(w.condition)?'☁️':/clear/i.test(w.condition)?'☀️':'◌';
    const city=document.createElement('b'); city.textContent=w.city;
    const temp=document.createElement('strong'); temp.textContent=`${Math.round(w.temperature_c)}°`;
    const desc=document.createElement('span'); desc.textContent=`${symbol} ${w.description}`;
    const meta=document.createElement('small'); meta.textContent=`Humidity ${w.humidity_pct}% · Wind ${w.wind_speed_mps} m/s`;
    card.append(city,temp,desc,meta); el.append(card);
  }
}

async function refresh() {
  try {
    const paths=['/metrics/overview','/alerts?limit=8','/intelligence','/metrics/demand/trend','/metrics/weather','/metrics/realism','/metrics/forecast-accuracy'];
    const [o,a,i,d,w,r,f]=await Promise.all(paths.map(path=>fetch(path).then(resp=>{if(!resp.ok)throw Error(path);return resp.json()})));
    document.querySelector('#status').textContent='● SYSTEM LIVE';
    document.querySelector('#cards').innerHTML=Object.entries({'Events processed':o.events_processed,'Orders':o.orders,'Low stock':o.low_stock_observations,'Active alerts':o.active_alerts,'Stockout rate':(100*o.stockout_rate).toFixed(1)+'%'}).map(([k,v])=>`<article><small>${k}</small><strong>${fmt(v)}</strong></article>`).join('');
    document.querySelector('#intelligence').innerHTML=`<b>${i.system_status.toUpperCase()}</b> · ${i.recommended_actions.slice(0,3).map(x=>`${x.explanation} ${x.recommended_action}`).join('<br>')||'No current risks detected.'}`;
    document.querySelector('#alerts').innerHTML=a.map(x=>`<p><b>${x.severity}</b> · ${x.type} · ${x.store_id} / ${x.product_id} — ${x.message}</p>`).join('')||'No alerts';
    document.querySelector('#realismCards').innerHTML=Object.entries({'Availability':`${(100*r.availability_rate).toFixed(1)}%`,'Service level · 7d':`${(100*r.service_level_7d).toFixed(1)}%`,'Lost sales · 7d':fmt(r.lost_sales_units_7d),'Waste cost · 7d':`€${fmt(r.waste_cost_7d)}`,'Supplier OTIF':`${(100*r.otif_rate).toFixed(1)}% · ${r.otif_status==='warming_up'?`${r.otif_observations} sample`: 'ready'}`}).map(([k,v])=>`<article><small>${k}</small><strong>${v}</strong></article>`).join('');
    document.querySelector('#forecastAccuracy').textContent=`Forecast backtest · ${f.method} · ${f.comparisons} comparisons · WAPE ${f.comparisons ? (100*f.wape).toFixed(1)+'%' : 'warming up'}`;
    drawDemandTrend(d); renderWeather(w);
  } catch (error) { document.querySelector('#status').textContent='Waiting for API / data'; }
}

refresh(); setInterval(refresh,15000);
