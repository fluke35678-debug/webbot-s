// Economy Page Logic

// --- Tab Navigation ---
function showSection(id) {
    document.querySelectorAll('.section-content').forEach(el => el.classList.add('hidden', 'fade-in'));
    document.getElementById(`section-${id}`).classList.remove('hidden');

    // Animate In
    setTimeout(() => {
        document.getElementById(`section-${id}`).classList.add('active');
    }, 10);

    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    event.currentTarget.classList.add('active');

    // Auto-refresh data based on section
    if (id === 'mining') updateMiningStats();
}

// --- Mining System ---
async function updateMiningStats() {
    try {
        const res = await fetch('/api/economy/mine/stats');
        const data = await res.json();

        document.getElementById('mining-rate').innerText = data.rate_per_hour + "/hr";
        document.getElementById('mining-pending').innerText = data.pending_rewards.toFixed(4);
        document.getElementById('mining-gpu').innerText = data.current_gpu.name;

        if (data.next_upgrade) {
            document.getElementById('mining-next-gpu').innerText = data.next_upgrade.name;
            document.getElementById('mining-cost').innerText = data.next_upgrade.cost;
        } else {
            document.getElementById('mining-next-gpu').innerText = "MAX LEVEL";
            document.getElementById('btn-upgrade-mining').disabled = true;
            document.getElementById('btn-upgrade-mining').innerText = "Maxed Out";
        }
    } catch (e) { console.error("Mining Sync Error", e); }
}

async function collectMining() {
    const btn = event.currentTarget;
    btn.disabled = true;
    try {
        const res = await fetch('/api/economy/mine/collect', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            Swal.fire({
                title: 'Collected!',
                text: data.message,
                icon: 'success',
                background: '#0a0e27',
                color: '#fff',
                timer: 2000,
                showConfirmButton: false
            });
            updateMiningStats();
            updateBalance(); // Global balance
        } else {
            Swal.fire({ title: 'Oops', text: data.message, icon: 'warning', background: '#0a0e27', color: '#fff' });
        }
    } catch (e) { }
    btn.disabled = false;
}

async function upgradeMining() {
    const cost = document.getElementById('mining-cost').innerText;
    const { isConfirmed } = await Swal.fire({
        title: 'Upgrade GPU?',
        text: `Buy next tier for ${cost} coins?`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'Buy',
        background: '#0a0e27',
        color: '#fff'
    });

    if (isConfirmed) {
        const res = await fetch('/api/economy/mine/upgrade', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            Swal.fire('Upgraded!', data.message, 'success');
            updateMiningStats();
            updateBalance();
        } else {
            Swal.fire('Failed', data.message, 'error');
        }
    }
}

// --- Fishing System ---
let isFishing = false;

async function castLine() {
    if (isFishing) return;
    isFishing = true;

    const btn = document.getElementById('btn-fish');
    const resultDiv = document.getElementById('fishing-result');
    const bobber = document.getElementById('fishing-bobber');

    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Waiting...';
    resultDiv.innerHTML = '';

    // Visual Animation
    bobber.style.animation = "bob 1s infinite alternate";

    // Wait random time (2-4s)
    await new Promise(r => setTimeout(r, 2000 + Math.random() * 2000));

    try {
        const res = await fetch('/api/economy/fish', { method: 'POST' });
        const data = await res.json();

        bobber.style.animation = ""; // Stop bobbing

        if (data.success) {
            // Success
            resultDiv.innerHTML = `<span class="text-success">${data.message}</span>`;
            updateBalance();
        } else {
            // Fail / Cooldown
            resultDiv.innerHTML = `<span class="text-danger">${data.message}</span>`;
        }
    } catch (e) {
        resultDiv.innerText = "Connection Error";
    }

    isFishing = false;
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-fish-fins"></i> CAST LINE';
}

// --- Pet System ---
async function interactPet(action) {
    try {
        const res = await fetch('/api/economy/pet/interact', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: action })
        });
        const data = await res.json();

        if (data.success) {
            const icon = action === 'FEED' ? '🍖' : '🎾';
            Swal.fire({
                icon: 'success',
                title: icon + ' ' + data.message,
                toast: true,
                position: 'bottom-end',
                showConfirmButton: false,
                timer: 2000,
                background: '#1e293b',
                color: '#fff'
            });
            setTimeout(() => location.reload(), 1500); // Reload to show new stats
        } else {
            Swal.fire('Error', data.message, 'error');
        }
    } catch (e) { }
}

// --- Global Helpers ---
async function updateBalance() {
    // Implement if header balance needs dynamic update
    // Usually user reloads page, but nice to have.
}

// Auto-run loop for mining pending display?
setInterval(() => {
    // Only if mining section is active
    if (!document.getElementById('section-mining').classList.contains('hidden')) {
        let current = parseFloat(document.getElementById('mining-pending').innerText || 0);
        let rate = parseFloat(document.getElementById('mining-rate').innerText || 0);
        // Estimate per second locally for visual smoothness
        if (rate > 0) {
            current += (rate / 3600);
            document.getElementById('mining-pending').innerText = current.toFixed(4);
        }
    }
}, 1000);
