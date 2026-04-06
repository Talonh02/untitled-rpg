// ============================================================
// UNTITLED RPG — Frontend Logic
// Talks to the Flask backend, renders game state
// ============================================================

let currentState = null;      // latest game state from server
let creationType = 'quick';   // 'quick' or 'custom'
let selectedArchetype = 'wanderer';
let isProcessing = false;     // prevent double-sends while waiting for AI

// ============================================================
// SCREEN MANAGEMENT
// ============================================================

function showScreen(id) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(id).classList.add('active');
}

function showCreation() {
    showScreen('creation-screen');
    loadArchetypes();
    document.getElementById('char-name').focus();
}

// ============================================================
// CHARACTER CREATION
// ============================================================

async function loadArchetypes() {
    // Auto-fill from saved profile
    try {
        const profileRes = await fetch('/api/profile');
        const profile = await profileRes.json();
        if (profile.name) document.getElementById('char-name').value = profile.name;
        if (profile.description) document.getElementById('char-description').value = profile.description;
        if (profile.archetype) selectedArchetype = profile.archetype;
    } catch (e) { /* no profile saved yet */ }

    try {
        const res = await fetch('/api/archetypes');
        const archetypes = await res.json();
        const list = document.getElementById('archetype-list');
        list.innerHTML = '';
        archetypes.forEach(a => {
            const div = document.createElement('div');
            div.className = 'archetype-option' + (a.key === selectedArchetype ? ' selected' : '');
            div.onclick = () => {
                selectedArchetype = a.key;
                document.querySelectorAll('.archetype-option').forEach(el => el.classList.remove('selected'));
                div.classList.add('selected');
            };
            div.innerHTML = `<strong>${a.name}</strong><br><span class="dim">${a.description}</span>`;
            list.appendChild(div);
        });
    } catch (e) {
        console.error('Failed to load archetypes:', e);
    }
}

function setCreationType(type, btn) {
    creationType = type;
    document.querySelectorAll('.creation-tabs .tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('quick-creation').style.display = type === 'quick' ? 'block' : 'none';
    document.getElementById('custom-creation').style.display = type === 'custom' ? 'block' : 'none';
}

async function startGame() {
    const name = document.getElementById('char-name').value.trim() || 'Stranger';
    const loading = document.getElementById('loading');
    loading.style.display = 'block';
    document.querySelector('.start-btn').disabled = true;

    const body = {
        name: name,
        type: creationType,
        archetype: selectedArchetype,
        description: document.getElementById('char-description')?.value || '',
    };

    try {
        const res = await fetch('/api/new-game', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body),
        });
        const data = await res.json();

        if (data.error) {
            loading.innerHTML = `<p style="color:var(--red)">Error: ${data.error}</p>`;
            return;
        }

        currentState = data.state;
        showScreen('game-screen');

        // Show character backstory then opening scene
        if (data.player?.backstory) {
            addNarration(data.player.backstory);
        }
        addNarration(data.narration);
        updateUI(data.state);
        document.getElementById('player-input').focus();
    } catch (e) {
        loading.innerHTML = `<p style="color:var(--red)">Connection error: ${e.message}</p>`;
    }
}

// ============================================================
// GAME ACTIONS
// ============================================================

async function submitAction() {
    if (isProcessing) return;
    const input = document.getElementById('player-input');
    const text = input.value.trim();
    if (!text) return;

    input.value = '';
    setProcessing(true);
    addPlayerInput(text);

    try {
        const res = await fetch('/api/action', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({text: text}),
        });
        const data = await res.json();
        handleResponse(data);
    } catch (e) {
        addSystem(`Connection error: ${e.message}`);
    }

    setProcessing(false);
    input.focus();
}

// Button actions skip the interpreter — cheaper and more reliable
async function buttonAction(type, targetId) {
    if (isProcessing) return;
    setProcessing(true);

    try {
        const res = await fetch('/api/action', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({button: type, target: targetId || ''}),
        });
        const data = await res.json();
        handleResponse(data);
    } catch (e) {
        addSystem(`Connection error: ${e.message}`);
    }

    setProcessing(false);
    document.getElementById('player-input').focus();
}

function setProcessing(val) {
    isProcessing = val;
    document.getElementById('player-input').disabled = val;
    document.getElementById('send-btn').disabled = val;
}

function handleResponse(data) {
    if (data.narration) addNarration(data.narration);
    if (data.dialogue) addDialogue(data.dialogue.speaker, data.dialogue.text);
    if (data.combat_text) addCombat(data.combat_text);
    if (data.system) data.system.forEach(msg => addSystem(msg));
    if (data.death) {
        addCombat(`You have died. Cause: ${data.death.cause}`);
        addSystem('--- GAME OVER ---');
    }
    if (data.state) {
        currentState = data.state;
        updateUI(data.state);
    }
}

// ============================================================
// NARRATIVE LOG — the scrolling center panel
// ============================================================

function addNarration(text) {
    if (!text) return;
    const log = document.getElementById('narrative-log');
    const div = document.createElement('div');
    div.className = 'narration';
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

function addDialogue(speaker, text) {
    if (!text) return;
    const log = document.getElementById('narrative-log');
    const div = document.createElement('div');
    div.className = 'dialogue';
    div.innerHTML = `<span class="speaker">${escapeHtml(speaker)}</span><p>${escapeHtml(text)}</p>`;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

function addCombat(text) {
    if (!text) return;
    const log = document.getElementById('narrative-log');
    const div = document.createElement('div');
    div.className = 'combat-text';
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

function addPlayerInput(text) {
    const log = document.getElementById('narrative-log');
    const div = document.createElement('div');
    div.className = 'player-input-echo';
    div.textContent = `> ${text}`;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

function addSystem(text) {
    const log = document.getElementById('narrative-log');
    const div = document.createElement('div');
    div.className = 'system-msg';
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

// ============================================================
// UI UPDATES — refresh all panels from state
// ============================================================

function updateUI(state) {
    if (!state || state.error) return;

    // Time bar
    document.getElementById('time-display').textContent =
        `${capitalize(state.time.slot)} · Day ${state.time.day} · ${capitalize(state.time.season)}`;

    // Player name + vitals
    document.getElementById('player-name').textContent = state.player.name;
    document.getElementById('vitals').innerHTML = `
        ${vitalBar('Health', state.player.health, 'health')}
        ${vitalBar('Hunger', state.player.hunger, 'hunger')}
        ${vitalBar('Fatigue', state.player.fatigue, 'fatigue')}
    `;

    // Equipment
    document.getElementById('equipment').innerHTML = `
        <div class="equip-row"><span class="dim">Weapon</span> ${escapeHtml(state.player.weapon)}</div>
        <div class="equip-row"><span class="dim">Armor</span> ${escapeHtml(state.player.armor)}</div>
        <div class="equip-row"><span class="dim">Coins</span> <span class="gold">${state.player.coins}c</span></div>
    `;

    // Location (with population if available)
    const loc = state.location;
    const pop = loc.population ? ` · pop. ${loc.population.toLocaleString()}` : '';
    document.getElementById('location-info').innerHTML = `
        <div class="location-name">${escapeHtml(loc.name)}</div>
        <div class="location-type">${escapeHtml(loc.type)}${loc.parent ? ` in ${escapeHtml(loc.parent)}` : ''}${pop}</div>
    `;

    // NPCs
    updateNpcList(state.npcs);

    // Nearby locations
    updateNearbyList(state.nearby);

    // Action buttons
    updateActionButtons(state);

    // Refresh active tab
    const activeTab = document.querySelector('#tab-content .tab-panel.active');
    if (activeTab) {
        const tabName = activeTab.id.replace('tab-', '');
        updateTab(tabName, state);
    }
}

function vitalBar(label, value, type) {
    return `
        <div class="vital">
            <span>${label}</span>
            <div class="bar"><div class="bar-fill ${type}" style="width:${value}%"></div></div>
            <span class="val">${value}</span>
        </div>
    `;
}

function updateNpcList(npcs) {
    const list = document.getElementById('npc-list');
    list.innerHTML = '';

    if (!npcs || npcs.length === 0) {
        list.innerHTML = '<div class="dim">Nobody here.</div>';
        return;
    }

    npcs.forEach(npc => {
        if (!npc.alive) return;
        const div = document.createElement('div');
        div.className = 'npc-entry';

        // Fate tier color (based on occupation/threat for now — full fate tier comes from backend)
        const fateTier = getFateTier(npc);
        const fateColor = `fate-${fateTier}`;

        div.innerHTML = `
            <div class="npc-name">
                <span class="fate-dot" style="background:var(--${fateColor})"></span>
                ${escapeHtml(npc.name)}
            </div>
            <div class="npc-details">
                ${npc.build ? `<span class="dim">${npc.build}</span> · ` : ''}
                <span class="threat-${npc.threat}">${npc.threat}</span>
                ${npc.met && npc.relationship !== 'stranger' ? ` · <span class="dim">${npc.relationship}</span>` : ''}
            </div>
            <div class="npc-actions">
                <button onclick="buttonAction('talk', '${npc.id}')">Talk</button>
                <button onclick="startBattle('${npc.id}')" class="danger" title="Round-by-round combat">Battle</button>
                <button onclick="visualizeScene('${npc.id}')" title="Generate portrait">Portrait</button>
            </div>
        `;
        list.appendChild(div);
    });
}

// Fate tier comes from backend now (exponentially distributed)
// common (60%), uncommon (25%), rare (10%), epic (3.5%), legendary (1.2%), mythic (0.3%)
function getFateTier(npc) {
    return npc.fate_tier || 'common';
}

function updateNearbyList(nearby) {
    const list = document.getElementById('nearby-list');
    list.innerHTML = '';

    if (!nearby || nearby.length === 0) {
        list.innerHTML = '<div class="dim">Nowhere to go.</div>';
        return;
    }

    nearby.forEach(place => {
        const arrow = place.dir === 'outside' ? '&uarr;' : place.dir === 'inside' ? '&darr;' : '&rarr;';
        const div = document.createElement('div');
        div.className = 'nearby-entry';
        div.innerHTML = `
            <button onclick="buttonAction('move', '${place.id}')" class="location-btn">
                ${arrow} ${escapeHtml(place.name)} <span class="dim">(${place.type})</span>
            </button>
        `;
        list.appendChild(div);
    });
}

function updateActionButtons(state) {
    const bar = document.getElementById('action-buttons');
    const hasNpcs = state.npcs && state.npcs.some(n => n.alive);
    bar.innerHTML = `
        <button onclick="buttonAction('observe')">Look Around</button>
        <button onclick="buttonAction('rest')">Rest</button>
        ${hasNpcs ? `<button onclick="buttonAction('trade', '${state.npcs.find(n => n.alive)?.id || ''}')">Trade</button>` : ''}
        <button onclick="visualizeScene()" class="visualize-btn">Visualize</button>
    `;
}

// ============================================================
// IMAGE GENERATION — "Visualize" button
// ============================================================

async function visualizeScene(npcId) {
    if (isProcessing) return;
    setProcessing(true);
    addSystem(npcId ? 'Generating portrait...' : 'Generating scene image...');

    try {
        const body = npcId ? {npc_id: npcId} : {};
        const res = await fetch('/api/visualize', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body),
        });
        const data = await res.json();

        if (data.image_url) {
            addImage(data.image_url);
        } else {
            addSystem(`Image failed: ${data.error || 'unknown error'}`);
        }
    } catch (e) {
        addSystem(`Image failed: ${e.message}`);
    }

    setProcessing(false);
}

function addImage(url) {
    const log = document.getElementById('narrative-log');
    const div = document.createElement('div');
    div.className = 'scene-image';
    div.innerHTML = `<img src="${url}" alt="Scene visualization" loading="lazy">`;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

// ============================================================
// TAB SYSTEM (right panel)
// ============================================================

function switchTab(name, btn) {
    document.querySelectorAll('.tab-bar .tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('#tab-content .tab-panel').forEach(p => p.classList.remove('active'));
    document.getElementById(`tab-${name}`).classList.add('active');
    if (currentState) updateTab(name, currentState);
}

function updateTab(name, state) {
    const panel = document.getElementById(`tab-${name}`);
    if (!panel) return;

    if (name === 'stats') {
        const s = state.player.stats;
        panel.innerHTML = `
            <div class="stats-grid">
                <div class="stat-group">
                    <h4>Physical</h4>
                    ${statRow('STR', s.strength)}${statRow('TGH', s.toughness)}
                    ${statRow('AGI', s.agility)}${statRow('ATT', s.attractiveness)}
                </div>
                <div class="stat-group">
                    <h4>Mental</h4>
                    ${statRow('INT', s.intelligence)}${statRow('DEP', s.depth)}
                    ${statRow('WIS', s.wisdom)}${statRow('PER', s.perception)}
                    ${statRow('WIL', s.willpower)}${statRow('EDU', s.education)}
                    ${statRow('CRE', s.creativity)}
                </div>
                <div class="stat-group">
                    <h4>Social</h4>
                    ${statRow('CHA', s.charisma)}${statRow('EMP', s.empathy)}
                    ${statRow('COU', s.courage)}${statRow('HON', s.honesty)}
                    ${statRow('HUM', s.humor)}${statRow('STB', s.stubbornness)}
                    ${statRow('AMB', s.ambition)}${statRow('LOY', s.loyalty)}
                </div>
            </div>
            <div class="stat-group">
                <h4>Status</h4>
                ${statRow('Days', state.player.days_alive)}
                ${statRow('Kills', state.player.kills)}
            </div>
            ${state.player.injuries.length ?
                `<div class="stat-group"><h4>Injuries</h4>${state.player.injuries.map(i =>
                    `<div class="injury">${escapeHtml(i.name)} (${i.severity})</div>`).join('')}</div>`
                : ''}
        `;
        // Hired units
        const units = state.player.hired_units || [];
        if (units.length) {
            panel.innerHTML += `
                <div class="stat-group">
                    <h4>Hired Units</h4>
                    ${units.map(u => `
                        <div class="unit-entry">
                            <div>${escapeHtml(u.name)} <span class="dim">&times;${u.count}</span></div>
                            <div class="dim" style="font-size:0.75rem">
                                ${escapeHtml(u.weapon)} · ${escapeHtml(u.armor)}
                                · morale ${u.morale} · ${u.cost_per_day}c/day
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        }
    } else if (name === 'inventory') {
        panel.innerHTML = `
            <div class="inv-section">
                <div class="equip-row"><span class="dim">Weapon:</span> ${escapeHtml(state.player.weapon)}</div>
                <div class="equip-row"><span class="dim">Armor:</span> ${escapeHtml(state.player.armor)}</div>
                <div class="equip-row"><span class="dim">Coins:</span> <span class="gold">${state.player.coins}c</span></div>
            </div>
            <hr>
            <div class="inv-items">
                ${state.player.inventory.length ?
                    state.player.inventory.map(i => `<div class="inv-item">${escapeHtml(String(i))}</div>`).join('')
                    : '<div class="dim">Nothing else.</div>'}
            </div>
        `;
    } else if (name === 'journal') {
        const knowledge = state.player.knowledge || [];
        panel.innerHTML = `
            <div class="journal-entries">
                ${knowledge.length ?
                    knowledge.map(k => `<div class="journal-entry">${escapeHtml(String(k))}</div>`).join('')
                    : '<div class="dim">Your journal is empty.</div>'}
            </div>
        `;
    } else if (name === 'lore') {
        loadLore(panel);
    } else if (name === 'map') {
        loadMap(panel, state);
    }
}

function statRow(label, value) {
    const color = value < 30 ? 'stat-low' : value > 65 ? 'stat-high' : '';
    return `<div class="stat-row"><span class="stat-label">${label}</span><span class="stat-val ${color}">${value}</span></div>`;
}

// ============================================================
// MAP — interactive SVG map with zoom levels
// ============================================================

let mapData = null;
let mapViewLevel = null;  // which parent we're zoomed into (null = world view)

async function loadMap(panel, state) {
    if (!mapData) {
        panel.innerHTML = '<div class="dim">Loading map...</div>';
        try {
            const res = await fetch('/api/map');
            mapData = await res.json();
        } catch (e) {
            panel.innerHTML = '<div class="dim">Map unavailable.</div>';
            return;
        }
    }
    renderMap(panel, state);
}

function renderMap(panel, state) {
    if (!mapData || !mapData.locations) {
        panel.innerHTML = '<div class="dim">No map data.</div>';
        return;
    }

    const locs = mapData.locations;
    const roads = mapData.roads;

    // Decide which locations to show based on zoom level
    let visible;
    if (mapViewLevel) {
        // Zoomed in: show children of this location
        visible = locs.filter(l => l.parent_id === mapViewLevel);
        // Also show the parent itself for context
        const parent = locs.find(l => l.id === mapViewLevel);
        if (parent) visible.unshift(parent);
    } else {
        // World view: show top-level locations (no parent, or continents/regions)
        visible = locs.filter(l => !l.parent_id || l.type === 'continent' || l.type === 'region');
        // If everything has a parent, show cities instead
        if (visible.length === 0) {
            visible = locs.filter(l => l.type === 'city' || l.type === 'region');
        }
        if (visible.length === 0) {
            visible = locs.slice(0, 20);
        }
    }

    if (visible.length === 0) {
        panel.innerHTML = '<div class="dim">Nothing to show at this zoom level.</div>';
        return;
    }

    // Calculate bounds for SVG viewBox
    const xs = visible.map(l => l.x);
    const ys = visible.map(l => l.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const padX = Math.max(50, (maxX - minX) * 0.15);
    const padY = Math.max(50, (maxY - minY) * 0.15);
    const vbX = minX - padX, vbY = minY - padY;
    const vbW = Math.max(100, maxX - minX + padX * 2);
    const vbH = Math.max(100, maxY - minY + padY * 2);

    // Build visible location IDs for road filtering
    const visIds = new Set(visible.map(l => l.id));

    // Filter roads to only those connecting visible locations
    const visRoads = roads.filter(r => visIds.has(r.from) && visIds.has(r.to));
    const locMap = {};
    visible.forEach(l => locMap[l.id] = l);

    // Size by type
    const typeRadius = {
        continent: 12, region: 8, city: 6, district: 4, building: 3, floor: 2, room: 2
    };

    // Build SVG
    let svg = `<svg viewBox="${vbX} ${vbY} ${vbW} ${vbH}" class="game-map" xmlns="http://www.w3.org/2000/svg">`;

    // Roads
    for (const road of visRoads) {
        const a = locMap[road.from], b = locMap[road.to];
        if (a && b) {
            svg += `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"
                     stroke="#2a2520" stroke-width="1" opacity="0.6"/>`;
            // Distance label at midpoint
            const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
            svg += `<text x="${mx}" y="${my + 3}" fill="#5a5248" font-size="${vbW/50}"
                     text-anchor="middle">${road.distance_km}km</text>`;
        }
    }

    // Locations
    for (const loc of visible) {
        const r = typeRadius[loc.type] || 4;
        const scaledR = r * (vbW / 400);
        const isCurrent = loc.is_current;
        const hasChildren = loc.children && loc.children.length > 0;

        // Circle
        const fillColor = isCurrent ? '#c4a35a' : '#3a3530';
        const strokeColor = isCurrent ? '#e0c070' : '#5a5248';
        svg += `<circle cx="${loc.x}" cy="${loc.y}" r="${scaledR}"
                 fill="${fillColor}" stroke="${strokeColor}" stroke-width="${scaledR/4}"
                 class="map-node" data-id="${loc.id}" data-has-children="${hasChildren}"
                 style="cursor:${hasChildren ? 'pointer' : 'default'}"/>`;

        // Label
        const fontSize = vbW / 40;
        svg += `<text x="${loc.x}" y="${loc.y - scaledR - fontSize * 0.3}"
                 fill="${isCurrent ? '#e0c070' : '#8a7e6e'}" font-size="${fontSize}"
                 text-anchor="middle" font-family="Inter, sans-serif">
                 ${escapeHtml(loc.name)}</text>`;

        // Population label (smaller, below)
        if (loc.population > 0) {
            svg += `<text x="${loc.x}" y="${loc.y + scaledR + fontSize}"
                     fill="#5a5248" font-size="${fontSize * 0.7}"
                     text-anchor="middle">pop ${loc.population.toLocaleString()}</text>`;
        }
    }

    svg += '</svg>';

    // Zoom controls
    const breadcrumb = mapViewLevel ?
        `<button class="map-zoom-btn" onclick="mapZoomOut()">&#8592; Zoom Out</button>
         <span class="dim"> viewing: ${escapeHtml(locMap[mapViewLevel]?.name || mapViewLevel)}</span>` :
        '<span class="dim">World View</span>';

    panel.innerHTML = `
        <div class="map-controls">${breadcrumb}</div>
        ${svg}
        <div class="map-legend dim" style="font-size:0.7rem;margin-top:0.3rem">
            Click a location to zoom in. Gold = you are here.
        </div>
    `;

    // Add click handlers for zooming
    panel.querySelectorAll('.map-node').forEach(node => {
        node.addEventListener('click', () => {
            const id = node.getAttribute('data-id');
            const hasChildren = node.getAttribute('data-has-children') === 'true';
            if (hasChildren) {
                mapViewLevel = id;
                renderMap(panel, currentState);
            } else {
                // Click on a leaf = move there
                buttonAction('move', id);
            }
        });
    });
}

function mapZoomOut() {
    if (!mapData || !mapViewLevel) return;
    // Find parent of current view level
    const current = mapData.locations.find(l => l.id === mapViewLevel);
    mapViewLevel = current?.parent_id || null;
    const panel = document.getElementById('tab-map');
    if (panel && currentState) renderMap(panel, currentState);
}

async function loadLore(panel) {
    panel.innerHTML = '<div class="dim">Loading lore...</div>';
    try {
        const res = await fetch('/api/lore');
        const lore = await res.json();
        if (lore.error) {
            panel.innerHTML = `<div class="dim">${lore.error}</div>`;
            return;
        }
        panel.innerHTML = `
            <div class="lore-section">
                ${lore.name ? `<div class="lore-section"><h4>${escapeHtml(lore.name)}</h4></div>` : ''}
                ${lore.era ? `<div class="dim">${escapeHtml(lore.era)}</div>` : ''}
                ${lore.tone ? `<div class="dim italic">${escapeHtml(lore.tone)}</div>` : ''}
                ${lore.themes?.length ? `<div class="lore-themes">${lore.themes.map(t => escapeHtml(t)).join(' · ')}</div>` : ''}
            </div>
            ${lore.factions && Object.keys(lore.factions).length ? `
                <div class="lore-section">
                    <h4>Factions</h4>
                    ${Object.entries(lore.factions).map(([name, data]) =>
                        `<div class="lore-faction"><strong>${escapeHtml(name)}</strong>${
                            typeof data === 'object' && data.goals?.length ? `: ${escapeHtml(data.goals[0])}` : ''
                        }</div>`
                    ).join('')}
                </div>
            ` : ''}
            ${lore.conflicts?.length ? `
                <div class="lore-section">
                    <h4>Active Conflicts</h4>
                    ${lore.conflicts.map(c =>
                        `<div class="lore-conflict">${escapeHtml(typeof c === 'object' ? (c.name || JSON.stringify(c)) : String(c))}</div>`
                    ).join('')}
                </div>
            ` : ''}
            ${lore.traditions?.length ? `
                <div class="lore-section">
                    <h4>Traditions</h4>
                    ${lore.traditions.slice(0, 5).map(t =>
                        `<div class="dim">${escapeHtml(typeof t === 'object' ? (t.name || JSON.stringify(t)) : String(t))}</div>`
                    ).join('')}
                </div>
            ` : ''}
        `;
    } catch (e) {
        panel.innerHTML = '<div class="dim">Failed to load lore.</div>';
    }
}

// ============================================================
// BATTLE SIMULATION — round-by-round playback
// ============================================================

async function startBattle(enemyId) {
    if (isProcessing) return;
    setProcessing(true);

    // For now: player always fights. Later: pre-battle options UI
    const body = {
        enemy_id: enemyId,
        player_fights: true,
        hold_companions: [],
    };

    try {
        const res = await fetch('/api/battle', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body),
        });
        const data = await res.json();

        if (data.error) {
            addSystem(`Battle error: ${data.error}`);
            setProcessing(false);
            return;
        }

        // Play back rounds with delays
        addSystem(`--- BATTLE BEGIN (${data.total_rounds} rounds) ---`);
        await playBattleRounds(data.rounds);
        addSystem(`--- ${data.summary} ---`);

        if (data.state) {
            currentState = data.state;
            updateUI(data.state);
        }
    } catch (e) {
        addSystem(`Battle error: ${e.message}`);
    }

    setProcessing(false);
}

async function playBattleRounds(rounds) {
    for (const rnd of rounds) {
        // Show round header
        const log = document.getElementById('narrative-log');
        const header = document.createElement('div');
        header.className = 'system-msg';
        header.textContent = `Round ${rnd.round}`;
        log.appendChild(header);

        // Show events
        for (const evt of rnd.events) {
            const div = document.createElement('div');
            div.className = evt.type === 'rout' ? 'combat-text' :
                            evt.type === 'miss' ? 'system-msg' : 'combat-text';
            div.textContent = evt.text;
            log.appendChild(div);
        }

        // Show HP bars for this round
        const hpDiv = document.createElement('div');
        hpDiv.className = 'battle-hp-snapshot';
        let hpHtml = '';
        for (const c of rnd.enemy_side) {
            if (c.type === 'unit') {
                const pct = c.start_count > 0 ? (c.count / c.start_count * 100) : 0;
                hpHtml += `<div class="battle-bar"><span class="dim">${escapeHtml(c.name)}</span> <span class="battle-count">${c.count}/${c.start_count}</span><div class="bar"><div class="bar-fill health" style="width:${pct}%"></div></div></div>`;
            } else {
                const pct = c.max_hp > 0 ? (c.hp / c.max_hp * 100) : 0;
                hpHtml += `<div class="battle-bar"><span class="dim">${escapeHtml(c.name)}</span> <span class="battle-count">${c.hp}/${c.max_hp}</span><div class="bar"><div class="bar-fill health" style="width:${pct}%"></div></div></div>`;
            }
        }
        for (const c of rnd.player_side) {
            if (c.type === 'unit') {
                const pct = c.start_count > 0 ? (c.count / c.start_count * 100) : 0;
                hpHtml += `<div class="battle-bar"><span class="gold">${escapeHtml(c.name)}</span> <span class="battle-count">${c.count}/${c.start_count}</span><div class="bar"><div class="bar-fill fatigue" style="width:${pct}%"></div></div></div>`;
            } else if (c.active) {
                const pct = c.max_hp > 0 ? (c.hp / c.max_hp * 100) : 0;
                hpHtml += `<div class="battle-bar"><span class="gold">${escapeHtml(c.name)}</span> <span class="battle-count">${c.hp}/${c.max_hp}</span><div class="bar"><div class="bar-fill fatigue" style="width:${pct}%"></div></div></div>`;
            }
        }
        hpDiv.innerHTML = hpHtml;
        log.appendChild(hpDiv);
        log.scrollTop = log.scrollHeight;

        // Delay between rounds (~500ms)
        await new Promise(resolve => setTimeout(resolve, 500));
    }
}

// ============================================================
// SAVE / LOAD
// ============================================================

async function saveGame() {
    try {
        const res = await fetch('/api/save', {method: 'POST'});
        const data = await res.json();
        if (data.success) {
            addSystem('Game saved.');
        } else {
            addSystem(`Save failed: ${data.error || 'unknown error'}`);
        }
    } catch (e) {
        addSystem(`Save failed: ${e.message}`);
    }
}

async function loadGame() {
    try {
        const res = await fetch('/api/load', {method: 'POST'});
        const data = await res.json();
        if (data.error) {
            alert(`Could not load: ${data.error}`);
            return;
        }
        currentState = data.state;
        showScreen('game-screen');
        addNarration(data.narration);
        updateUI(data.state);
        document.getElementById('player-input').focus();
    } catch (e) {
        alert(`Load failed: ${e.message}`);
    }
}

// ============================================================
// KEYBOARD HANDLING
// ============================================================

document.addEventListener('keydown', e => {
    // Enter key sends action from the game input
    if (e.key === 'Enter' && !e.shiftKey) {
        const active = document.activeElement;
        if (active?.id === 'player-input') {
            e.preventDefault();
            submitAction();
        }
    }
});

// ============================================================
// UTILITIES
// ============================================================

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function capitalize(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
}
