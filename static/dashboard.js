// Theme Logic
function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const newTheme = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    
    if (barChartInstance) barChartInstance.options.scales.x.ticks.color = newTheme === 'dark' ? '#fff' : '#666';
    if (barChartInstance) barChartInstance.options.scales.y.ticks.color = newTheme === 'dark' ? '#fff' : '#666';
    if (barChartInstance) barChartInstance.options.plugins.legend.labels.color = newTheme === 'dark' ? '#fff' : '#666';
    if (pieChartInstance) pieChartInstance.options.plugins.legend.labels.color = newTheme === 'dark' ? '#fff' : '#666';
    if (barChartInstance) barChartInstance.update();
    if (pieChartInstance) pieChartInstance.update();
}

const savedTheme = localStorage.getItem('theme');
if (savedTheme) document.documentElement.setAttribute('data-theme', savedTheme);

// State
let allAttendance = [];
let allUsers = [];
let barChartInstance = null;
let pieChartInstance = null;

async function init() {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('dateFilter').value = today;
    await fetchData();
    setInterval(fetchData, 10000); 
}

async function fetchData() {
    try {
        const [attRes, usersRes] = await Promise.all([ fetch('/attendance'), fetch('/users') ]);
        allAttendance = await attRes.json();
        allUsers = await usersRes.json();
        if (allAttendance.error) allAttendance = [];
        if (allUsers.error) allUsers = [];
        filterData();
        renderUserTable();
    } catch (e) { console.error("Failed to fetch data", e); }
}

function filterData() {
    const search = document.getElementById('searchInput').value.toLowerCase();
    const date = document.getElementById('dateFilter').value;
    
    const filteredAtt = allAttendance.filter(r => {
        const mSearch = (r.name && r.name.toLowerCase().includes(search)) || (r.roll && r.roll.toLowerCase().includes(search));
        const mDate = date ? (r.date === date) : true;
        return mSearch && mDate;
    });

    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = filteredAtt.map(r => `
        <tr>
            <td>${r.roll || '-'}</td>
            <td><strong>${r.name || 'Unknown'}</strong></td>
            <td>${r.date || '-'}</td>
            <td>${r.timestamp || '-'}</td>
            <td><span class="status-badge">Present</span></td>
        </tr>
    `).join('');

    const totalStudents = allUsers.length;
    const targetDate = date || new Date().toISOString().split('T')[0];
    const todayAtt = allAttendance.filter(a => a.date === targetDate);
    const presentRolls = new Set(todayAtt.map(a => a.roll));
    const presentCount = presentRolls.size;
    const absentCount = Math.max(0, totalStudents - presentCount);

    document.getElementById('total-students').innerText = totalStudents;
    document.getElementById('present-today').innerText = presentCount;
    document.getElementById('absent-today').innerText = absentCount;

    updateCharts(filteredAtt, presentCount, absentCount);
}

function renderUserTable() {
    const search = document.getElementById('searchInput').value.toLowerCase();
    const filteredUsers = allUsers.filter(r => (r.name && r.name.toLowerCase().includes(search)) || (r.roll && r.roll.toLowerCase().includes(search)));
    
    const tbody = document.getElementById('userTableBody');
    tbody.innerHTML = filteredUsers.map(u => `
        <tr>
            <td>${u.roll}</td>
            <td><strong>${u.name}</strong></td>
            <td>
                <button class="action-btn hist" onclick="viewHistory('${u.roll}', '${u.name}')">View History</button>
                <button class="action-btn del" onclick="deleteUser('${u.roll}', '${u.name}')">Delete User</button>
            </td>
        </tr>
    `).join('');
}

async function deleteUser(roll, name) {
    if(confirm(`Are you sure you want to completely remove ${name} (${roll})? They will need to re-register.`)) {
        try {
            const res = await fetch(`/user/${roll}`, { method: 'DELETE' });
            const data = await res.json();
            if(data.status === 'success') {
                alert(`${name} deleted successfully.`);
                fetchData();
            } else { alert("Failed to delete user: " + data.error); }
        } catch(e) { alert("Error connecting to server."); }
    }
}

async function resetAttendance() {
    if(confirm("DANGER: This will permanently delete ALL attendance records for all dates! Are you sure?")) {
        try {
            const res = await fetch(`/reset_attendance`, { method: 'POST' });
            const data = await res.json();
            if(data.status === 'success') {
                alert(`All attendance records wiped.`);
                fetchData();
            } else { alert("Failed to reset: " + data.error); }
        } catch(e) { alert("Error connecting to server."); }
    }
}

function viewHistory(roll, name) {
    const hist = allAttendance.filter(a => a.roll === roll);
    document.getElementById('modalTitle').innerText = `History for ${name} (${roll})`;
    
    const mBody = document.getElementById('modalBody');
    if(hist.length === 0) {
        mBody.innerHTML = "<p>No attendance records found.</p>";
    } else {
        mBody.innerHTML = `<ul style="list-style-type:none; padding:0;">` + 
            hist.map(h => `<li style="padding:10px; border-bottom:1px solid var(--border-color);">${h.date} at ${h.timestamp} - <span style="color:#2ecc71;">Present</span></li>`).join('') +
            `</ul>`;
    }
    
    document.getElementById('historyModal').style.display = 'block';
}

function closeModal() { document.getElementById('historyModal').style.display = 'none'; }

function updateCharts(attendanceData, presentCount, absentCount) {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const textColor = isDark ? '#fff' : '#666';

    const counts = {};
    attendanceData.forEach(a => { counts[a.name] = (counts[a.name] || 0) + 1; });
    const sorted = Object.entries(counts).sort((a,b) => b[1] - a[1]).slice(0, 10);
    const labels = sorted.map(i => i[0]);
    const dataVals = sorted.map(i => i[1]);

    if (barChartInstance) barChartInstance.destroy();
    const ctxBar = document.getElementById('barChart').getContext('2d');
    barChartInstance = new Chart(ctxBar, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Attendance Count', data: dataVals,
                backgroundColor: 'rgba(52, 152, 219, 0.7)', borderColor: 'rgba(52, 152, 219, 1)', borderWidth: 1, borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { labels: { color: textColor } }, title: { display: true, text: 'Top 10 Attendance', color: textColor } },
            scales: { y: { beginAtZero: true, ticks: { color: textColor } }, x: { ticks: { color: textColor } } }
        }
    });

    if (pieChartInstance) pieChartInstance.destroy();
    const ctxPie = document.getElementById('pieChart').getContext('2d');
    pieChartInstance = new Chart(ctxPie, {
        type: 'doughnut',
        data: {
            labels: ['Present', 'Absent'],
            datasets: [{ data: [presentCount, absentCount], backgroundColor: ['rgba(46, 204, 113, 0.8)', 'rgba(231, 76, 60, 0.8)'], borderWidth: 0 }]
        },
        options: {
            responsive: true,
            plugins: { legend: { position: 'bottom', labels: { color: textColor } }, title: { display: true, text: 'Daily Overview', color: textColor } }
        }
    });
}

function exportCSV() {
    if (allAttendance.length === 0) return alert("No data to export!");
    let csvContent = "data:text/csv;charset=utf-8,Roll Number,Name,Date,Time,Status\n";
    allAttendance.forEach(r => { csvContent += `${r.roll},${r.name},${r.date},${r.timestamp},Present\n`; });
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `attendance_export.csv`);
    document.body.appendChild(link); link.click(); link.remove();
}

window.onload = init;
