with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = 'function updateCellDisplay(cell, colKey, val) {'
replacement = '''async function runCheck(e, rIdx, cIdx) {
      if (e) { e.stopPropagation(); e.preventDefault(); }
      const rec = currentRecords[rIdx];
      if (!rec) return;
      const curp = rec.curp;
      const cell = document.getElementById(cell-+rIdx+-+cIdx);
      if (!curp) {
        showToast("Se requiere CURP. Por favor ingresa el CURP para procesar.", "warning");
        if (cell) updateCellDisplay(cell, 'results', "SIN CURP");
        return;
      }
      if (cell) cell.innerHTML = <span style="color:#aaa;">Verificando...</span>;
      try {
        const res = await fetch(BASE_PATH + '/api/check_curp', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ curp: curp })
        });
        if (res.status === 401) { showLockScreen(); return; }
        const data = await res.json();
        
        let tag = '';
        if (data.status === 'ON') {
           tag = 'HIT';
        } else if (data.status === 'OFF') {
           tag = 'DEAD';
        } else {
           tag = data.detail || 'ERROR';
        }
        
        // Save to db
        await fetch(BASE_PATH + '/api/records/' + rec.id, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ field: 'results', value: tag })
        });
        rec.results = tag;
        if (cell) updateCellDisplay(cell, 'results', tag);
        
      } catch (err) {
        showToast("Error de conexion", "error");
        if (cell) updateCellDisplay(cell, 'results', rec.results || "");
      }
    }

    function updateCellDisplay(cell, colKey, val) {'''
content = content.replace(target, replacement)

# Now modify the part inside renderRows that renders results
target2 = '''} else if (col.key === 'results') {
              let tagBadge = '';
              if (rawVal === 'HIT') tagBadge = '<span class="tag-btn hit">HIT</span>';
              else if (rawVal === 'DEAD') tagBadge = '<span class="tag-btn dead">DEAD</span>';
              displayContent = <span>\</span> \;
            }'''
replacement2 = '''} else if (col.key === 'results') {
              let displayUI = '';
              if (!rawVal) {
                 displayUI = <button class="btn check-btn" style="padding:4px 10px; border-radius:4px; font-weight:bold; background:#ec0000; color:white; border:none; cursor:pointer;" onclick="runCheck(event, \, \)">Check</button>;
              } else if (rawVal === 'HIT') {
                 displayUI = '<span class="tag-btn hit" style="width:100%;text-align:center;display:inline-block;padding:4px;background:var(--color-primary-ring);color:#4ade80;">HIT</span>';
              } else if (rawVal === 'DEAD') {
                 displayUI = '<span class="tag-btn dead" style="width:100%;text-align:center;display:inline-block;padding:4px;background:rgba(255,255,255,0.1);color:#f87171;">DEAD</span>';
              } else {
                 displayUI = <span class="tag-btn error-lbl" style="flex:1; background:rgba(251,191,36,0.1); color:#fbbf24; border:1px solid #fbbf24; white-space: nowrap; overflow:hidden; text-overflow:ellipsis; padding:2px 6px; border-radius:4px; display:inline-block; font-size:10px;" title="\">\</span>;
                 displayUI += <button class="btn check-btn" style="margin-left:5px; padding:2px 5px; cursor:pointer;" onclick="runCheck(event, \, \)" title="Reintentar">?</button>;
              }
              displayContent = <div style="display:flex; align-items:center; width:100%; justify-content:center;">\</div>;
            }'''
content = content.replace(target2, replacement2)


# And also update the updateCellDisplay for 'results'
target3 = '''} else if (colKey === 'results') {
        let tagBadge = '';
        if (val === 'HIT') tagBadge = '<span class="tag-btn hit">HIT</span>';
        else if (val === 'DEAD') tagBadge = '<span class="tag-btn dead">DEAD</span>';
        displayContent = <span>\</span> \;
      }'''
replacement3 = '''} else if (colKey === 'results') {
        let displayUI = '';
        if (!val) {
           displayUI = <button class="btn check-btn" style="padding:4px 10px; border-radius:4px; font-weight:bold; background:#ec0000; color:white; border:none; cursor:pointer;" onclick="runCheck(event, cell.dataset.rowIdx, cell.dataset.colIdx)">Check</button>;
        } else if (val === 'HIT') {
           displayUI = '<span class="tag-btn hit" style="width:100%;text-align:center;display:inline-block;padding:4px;background:var(--color-primary-ring);color:#4ade80;">HIT</span>';
        } else if (val === 'DEAD') {
           displayUI = '<span class="tag-btn dead" style="width:100%;text-align:center;display:inline-block;padding:4px;background:rgba(255,255,255,0.1);color:#f87171;">DEAD</span>';
        } else {
           displayUI = <span class="tag-btn error-lbl" style="flex:1; background:rgba(251,191,36,0.1); color:#fbbf24; border:1px solid #fbbf24; white-space: nowrap; overflow:hidden; text-overflow:ellipsis; padding:2px 6px; border-radius:4px; display:inline-block; font-size:10px;" title="\">\</span>;
           displayUI += <button class="btn check-btn" style="margin-left:5px; padding:2px 5px; cursor:pointer;" onclick="runCheck(event, cell.dataset.rowIdx, cell.dataset.colIdx)" title="Reintentar">?</button>;
        }
        displayContent = <div style="display:flex; align-items:center; width:100%; justify-content:center;">\</div>;
      }'''
content = content.replace(target3, replacement3)


with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
