from flask import Flask, Response
app = Flask(__name__)

HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Real-Time Negative Pressure Monitor</title>
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
  <h1>Live Negative Pressure</h1>
  <!-- Error Banner -->
  <div id="error-banner" style="color:red; font-weight:bold;"></div>
  <div id="chart" style="width:600px;height:400px;"></div>

  <h2>All Readings (Values & Errors)</h2>
  <table border="1" cellpadding="5">
    <thead>
      <tr><th>Device</th><th>Time</th><th>Value/Error</th></tr>
    </thead>
    <tbody id="merged-table"></tbody>
  </table>

  <script>
    // Initialize traces
    Plotly.newPlot('chart', [
      {x: [], y: [], mode: 'lines+markers', name: 'neg-pressure-device-1', type: 'scatter'},
      {x: [], y: [], mode: 'lines+markers', name: 'neg-pressure-device-2', type: 'scatter'}
    ], {yaxis:{title:'cmH2O'}, xaxis:{type:'date'}});

    const ws = new WebSocket('ws://127.0.0.1:6789');
    const maxPoints = 10;
    // Store merged entries
    const merged = [];

    ws.addEventListener('open', () => console.log('WS connected'));
    ws.addEventListener('message', e => {
      const msg = JSON.parse(e.data);
      const errorBanner = document.getElementById('error-banner');
      // Display error banner if needed
      if (msg.error) {
        errorBanner.textContent = `⚠️ ${msg.device} ERROR: ${msg.message}`;
      } else {
        errorBanner.textContent = '';
      }
      // Plot chart value or null gap
      const yVal = msg.error ? null : msg.value;
      const idx = ['neg-pressure-device-1','neg-pressure-device-2'].indexOf(msg.device);
      Plotly.extendTraces('chart', { x: [[new Date(msg.time)]], y: [[yVal]] }, [idx]);
      const gd = document.getElementById('chart');
      gd.data[idx].x = gd.data[idx].x.slice(-maxPoints);
      gd.data[idx].y = gd.data[idx].y.slice(-maxPoints);
      Plotly.update('chart', {}, {}, [idx]);

      // Add to merged array
      merged.push({
        device: msg.device,
        time: new Date(msg.time),
        display: msg.error ? 'ERROR' : msg.value.toFixed(1)
      });
      // Sort by timestamp
      merged.sort((a,b) => a.time - b.time);

      // Rebuild table
      const tbody = document.getElementById('merged-table');
      tbody.innerHTML = '';
      merged.forEach(entry => {
        const tr = document.createElement('tr');
        const tdDev = document.createElement('td'); tdDev.textContent = entry.device;
        const tdTime = document.createElement('td'); tdTime.textContent = entry.time.toLocaleString();
        const tdVal = document.createElement('td'); tdVal.textContent = entry.display;
        tr.appendChild(tdDev);
        tr.appendChild(tdTime);
        tr.appendChild(tdVal);
        tbody.appendChild(tr);
      });
    });
  </script>
</body>
</html>'''

@app.route('/')
def index():
    return Response(HTML, mimetype='text/html')

if __name__=='__main__':
    app.run(host='127.0.0.1', port=5002)