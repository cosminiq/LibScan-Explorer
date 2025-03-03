// Global variables
let libraries = [];
let uniqueLibraries = [];

// DOM elements
const csvFileInput = document.getElementById('csvFileInput');
const searchInput = document.getElementById('searchInput');
const searchButton = document.getElementById('searchButton');
const sortSelect = document.getElementById('sortSelect');
const libraryContainer = document.getElementById('libraryContainer');
const loadingIndicator = document.getElementById('loadingIndicator');
const initialMessage = document.getElementById('initialMessage');
const noResults = document.getElementById('noResults');
const libraryStats = document.getElementById('libraryStats');
const totalLibrariesElement = document.getElementById('totalLibraries');
const uniqueLibrariesElement = document.getElementById('uniqueLibraries');
const withVersionsElement = document.getElementById('withVersions');
const detailModal = document.getElementById('detailModal');
const modalTitle = document.getElementById('modalTitle');
const modalContent = document.getElementById('modalContent');
const closeButton = document.querySelector('.close-button');
const generationDateElement = document.getElementById('generationDate');

// Set generation date
const currentDate = new Date();
generationDateElement.textContent = currentDate.toLocaleDateString('ro-RO');

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    csvFileInput.addEventListener('change', handleFileUpload);
    searchButton.addEventListener('click', filterLibraries);
    searchInput.addEventListener('keyup', (e) => {
        if (e.key === 'Enter') {
            filterLibraries();
        }
    });
    sortSelect.addEventListener('change', () => {
        sortLibraries(sortSelect.value);
        renderLibraries();
    });
    closeButton.addEventListener('click', () => {
        detailModal.classList.add('hidden');
    });
    
    // Close modal when clicking outside of it
    window.addEventListener('click', (e) => {
        if (e.target === detailModal) {
            detailModal.classList.add('hidden');
        }
    });
});

// Function to handle file upload
function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    // Show loading indicator
    loadingIndicator.classList.remove('hidden');
    initialMessage.classList.add('hidden');
    
    const reader = new FileReader();
    
    reader.onload = function(e) {
        const csvData = e.target.result;
        parseCSV(csvData);
    };
    
    reader.onerror = function() {
        alert('A apărut o eroare la citirea fișierului.');
        loadingIndicator.classList.add('hidden');
    };
    
    reader.readAsText(file);
}

// Function to parse CSV data - Revised for reliability
function parseCSV(csvData) {
    try {
        // Split the data into rows
        const rows = csvData.split('\n');
        
        // Extract the headers
        const headers = rows[0].split(',');
        
        // Clear previous data
        libraries = [];
        
        // Process each row
        for (let i = 1; i < rows.length; i++) {
            if (!rows[i].trim()) continue; // Skip empty rows
            
            // Simple CSV parsing for standard format
            const values = rows[i].split(',');
            
            // Create library object with matching headers
            const library = {};
            for (let j = 0; j < headers.length; j++) {
                library[headers[j]] = j < values.length ? values[j] : '';
            }
            
            libraries.push(library);
        }
        
        console.log("Parsed libraries:", libraries.length);
        
        // Process the libraries to get unique ones
        processLibraries();
        
        // Sort libraries by name initially
        sortLibraries('name');
        
        // Update stats
        updateStats();
        
        // Render the libraries
        renderLibraries();
        
        // Hide loading indicator and show stats
        loadingIndicator.classList.add('hidden');
        libraryStats.classList.remove('hidden');
    } catch (error) {
        console.error("Error parsing CSV:", error);
        alert("A apărut o eroare la procesarea datelor CSV: " + error.message);
        loadingIndicator.classList.add('hidden');
    }
}

// Function to process libraries and get unique ones
// Function to process libraries and get unique ones


// Function to process libraries and get unique ones
function processLibraries() {
    const libraryMap = new Map();
    
    // Group libraries by a unique combination of name, github_url, and homepage
    libraries.forEach(lib => {
        // Skip entries that don't have name, github_url, or homepage
        if (!lib.name || !lib.github_url || !lib.homepage) return;
        
        // Create a unique key based on name, github_url, and homepage
        const key = `${lib.name.toLowerCase()}-${lib.github_url.toLowerCase()}-${lib.homepage.toLowerCase()}`;
        
        if (!libraryMap.has(key)) {
            libraryMap.set(key, {
                ...lib,
                filesArray: lib.files_found_in ? [lib.files_found_in] : []
            });
        } else {
            const existing = libraryMap.get(key);
            // Combine the files found in each library and remove duplicates
            if (lib.files_found_in) {
                existing.filesArray.push(lib.files_found_in);
            }
            // Update the existing library with any missing information (in case some fields are empty)
            Object.keys(lib).forEach(key => {
                if (!existing[key] && lib[key]) {
                    existing[key] = lib[key];
                }
            });
        }
    });
    
    // Convert the map to an array of unique libraries
    uniqueLibraries = Array.from(libraryMap.values());
    console.log("Unique libraries:", uniqueLibraries.length);
    
    // Process files_found_in for each unique library
    uniqueLibraries.forEach(lib => {
        if (lib.filesArray && lib.filesArray.length > 0) {
            // Join the files array and remove duplicates
            const filesSet = new Set();
            lib.filesArray.forEach(fileStr => {
                if (typeof fileStr === 'string') {
                    fileStr.split(',').forEach(f => {
                        const trimmed = f.trim();
                        if (trimmed) filesSet.add(trimmed);
                    });
                }
            });
            lib.files_found_in = Array.from(filesSet).join(', ');
        }
    });
}



// Function to sort libraries
function sortLibraries(sortBy) {
    uniqueLibraries.sort((a, b) => {
        const valueA = (a[sortBy] || '').toLowerCase();
        const valueB = (b[sortBy] || '').toLowerCase();
        return valueA.localeCompare(valueB);
    });
}

// Function to filter libraries based on search input
function filterLibraries() {
    const searchTerm = searchInput.value.toLowerCase();
    
    if (!searchTerm) {
        renderLibraries(uniqueLibraries);
        return;
    }
    
    const filteredLibraries = uniqueLibraries.filter(lib => {
        return Object.values(lib).some(value => {
            if (typeof value === 'string') {
                return value.toLowerCase().includes(searchTerm);
            }
            return false;
        });
    });
    
    renderLibraries(filteredLibraries);
}

// Function to update statistics
function updateStats() {
    totalLibrariesElement.textContent = libraries.length;
    uniqueLibrariesElement.textContent = uniqueLibraries.length;
    
    const withVersions = uniqueLibraries.filter(lib => 
        lib.version && lib.version.trim() !== ''
    ).length;
    
    withVersionsElement.textContent = withVersions;
}

// Function to render libraries
function renderLibraries(libsToRender = uniqueLibraries) {
    libraryContainer.innerHTML = '';
    
    if (libsToRender.length === 0) {
        noResults.classList.remove('hidden');
        return;
    }
    
    noResults.classList.add('hidden');
    
    libsToRender.forEach(lib => {
        const card = createLibraryCard(lib);
        libraryContainer.appendChild(card);
    });
}

// Function to create a library card
function createLibraryCard(lib) {
    const card = document.createElement('div');
    card.className = 'library-card';
    
    const versionStatus = getVersionStatus(lib.version, lib.latest_version);
    
    card.innerHTML = `
        <div class="card-header">
            <h2>${lib.name || 'Bibliotecă necunoscută'}</h2>
        </div>
        <div class="card-body">
            <div class="library-info">
                <div class="info-item">
                    <span class="info-label">Versiune:</span>
                    <span>${lib.version || 'N/A'}</span>
                    ${versionStatus.badge}
                </div>
                <div class="info-item">
                    <span class="info-label">Autor:</span>
                    <span>${lib.author || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Sursă:</span>
                    <span>${lib.source || 'N/A'}</span>
                </div>
            </div>
            <button class="view-details">Vezi detalii</button>
        </div>
    `;
    
    // Add click event to view details
    card.querySelector('.view-details').addEventListener('click', () => {
        showLibraryDetails(lib);
    });
    
    return card;
}

// Function to get version status
function getVersionStatus(version, latestVersion) {
    if (!version || !latestVersion) {
        return {
            status: 'unknown',
            badge: '<span class="version-badge version-unknown">Necunoscută</span>'
        };
    }
    
    if (version === latestVersion) {
        return {
            status: 'current',
            badge: '<span class="version-badge version-current">Actualizată</span>'
        };
    }
    
    return {
        status: 'outdated',
        badge: '<span class="version-badge version-outdated">Învechită</span>'
    };
}

// Function to show library details in modal
function showLibraryDetails(lib) {
    modalTitle.textContent = lib.name || 'Detalii Bibliotecă';
    
    const versionStatus = getVersionStatus(lib.version, lib.latest_version);
    
    let githubLink = '';
    if (lib.github_url) {
        githubLink = `<a href="${lib.github_url}" target="_blank">${lib.github_url}</a>`;
    } else {
        githubLink = 'N/A';
    }
    
    let homepageLink = '';
    if (lib.homepage) {
        homepageLink = `<a href="${lib.homepage}" target="_blank">${lib.homepage}</a>`;
    } else {
        homepageLink = 'N/A';
    }
    
    const files = lib.files_found_in ? lib.files_found_in.split(',').map(file => file.trim()) : [];
    
    modalContent.innerHTML = `
        <div class="modal-section">
            <h3>Informații Generale</h3>
            <div class="info-item">
                <span class="info-label">Versiune:</span>
                <span>${lib.version || 'N/A'}</span>
                ${versionStatus.badge}
            </div>
            <div class="info-item">
                <span class="info-label">Versiune Recentă:</span>
                <span>${lib.latest_version || 'N/A'}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Autor:</span>
                <span>${lib.author || 'N/A'}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Sursă:</span>
                <span>${lib.source || 'N/A'}</span>
            </div>
        </div>
        
        <div class="modal-section">
            <h3>Descriere</h3>
            <p>${lib.description || 'Nu există descriere disponibilă.'}</p>
        </div>
        
        <div class="modal-section">
            <h3>Link-uri</h3>
            <div class="info-item">
                <span class="info-label">GitHub:</span>
                <span>${githubLink}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Homepage:</span>
                <span>${homepageLink}</span>
            </div>
        </div>
        
        <div class="modal-section">
            <h3>Fișiere Găsite (${files.length})</h3>
            <div class="file-list">
                ${files.length > 0 ? files.join('\n') : 'Nu există fișiere disponibile.'}
            </div>
        </div>
    `;
    
    detailModal.classList.remove('hidden');
}