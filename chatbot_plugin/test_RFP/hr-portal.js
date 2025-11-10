// RFP Chatbot JavaScript Functionality
document.addEventListener('DOMContentLoaded', function() {
    initializeRFPChatbot();
});

function initializeRFPChatbot() {
    setupNavigation();
    setupSearch();
    setupSidebarNavigation();
    setupResponsiveFeatures();
    
    // Show welcome message
}

// Navigation functionality
function setupNavigation() {
    const navLinks = document.querySelectorAll('.nav-link');
    
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Remove active class from all nav links
            navLinks.forEach(l => l.classList.remove('active'));
            
            // Add active class to clicked link
            this.classList.add('active');
            
            // Handle navigation based on href
            const href = this.getAttribute('href');
            handleNavigation(href);
        });
    });
}

// Sidebar navigation functionality
function setupSidebarNavigation() {
    const sidebarLinks = document.querySelectorAll('.sidebar-nav a');
    const policySections = document.querySelectorAll('.policy-section');
    
    sidebarLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Remove active class from all sidebar links
            sidebarLinks.forEach(l => l.classList.remove('active'));
            
            // Add active class to clicked link
            this.classList.add('active');
            
            // Get target section
            const targetSection = this.getAttribute('data-section');
            
            // Hide all policy sections
            policySections.forEach(section => {
                section.classList.remove('active');
            });
            
            // Show target section
            const target = document.getElementById(targetSection);
            if (target) {
                target.classList.add('active');
                
                // Smooth scroll to top of content area
                document.querySelector('.content-area').scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
            
            // Update URL hash
            window.location.hash = targetSection;
        });
    });
    
    // Handle initial load with hash
    handleInitialHash();
}

// Search functionality
function setupSearch() {
    const searchInput = document.getElementById('searchInput');
    let searchTimeout;
    
    searchInput.addEventListener('input', function() {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            performSearch(this.value.trim());
        }, 300);
    });
    
    searchInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            performSearch(this.value.trim());
        }
    });
}

// Perform search across policy content
function performSearch(query) {
    if (!query) {
        resetSearch();
        return;
    }
    
    const policySections = document.querySelectorAll('.policy-section');
    const sidebarLinks = document.querySelectorAll('.sidebar-nav a');
    let foundResults = false;
    
    // Hide all sections first
    policySections.forEach(section => {
        section.classList.remove('active');
    });
    
    // Remove active from sidebar links
    sidebarLinks.forEach(link => {
        link.classList.remove('active');
    });
    
    // Search through each section
    policySections.forEach(section => {
        const content = section.textContent.toLowerCase();
        const searchTerm = query.toLowerCase();
        
        if (content.includes(searchTerm)) {
            section.classList.add('active');
            foundResults = true;
            
            // Highlight search terms
            highlightSearchTerms(section, searchTerm);
            
            // Activate corresponding sidebar link
            const sectionId = section.id;
            const correspondingLink = document.querySelector(`[data-section="${sectionId}"]`);
            if (correspondingLink) {
                correspondingLink.classList.add('active');
            }
        }
    });
    
    if (!foundResults) {
        showNoResults(query);
    }
}

// Highlight search terms in content
function highlightSearchTerms(section, searchTerm) {
    const walker = document.createTreeWalker(
        section,
        NodeFilter.SHOW_TEXT,
        null,
        false
    );
    
    const textNodes = [];
    let node;
    
    while (node = walker.nextNode()) {
        textNodes.push(node);
    }
    
    textNodes.forEach(textNode => {
        const parent = textNode.parentNode;
        if (parent.tagName === 'SCRIPT' || parent.tagName === 'STYLE') return;
        
        const text = textNode.textContent;
        const regex = new RegExp(`(${escapeRegExp(searchTerm)})`, 'gi');
        
        if (regex.test(text)) {
            const highlightedText = text.replace(regex, '<mark class="search-highlight">$1</mark>');
            const wrapper = document.createElement('span');
            wrapper.innerHTML = highlightedText;
            parent.replaceChild(wrapper, textNode);
        }
    });
}

// Reset search results
function resetSearch() {
    // Remove all highlights
    const highlights = document.querySelectorAll('.search-highlight');
    highlights.forEach(highlight => {
        const parent = highlight.parentNode;
        parent.replaceChild(document.createTextNode(highlight.textContent), highlight);
        parent.normalize();
    });
    
    // Show default section (RFP overview)
    const policySections = document.querySelectorAll('.policy-section');
    const sidebarLinks = document.querySelectorAll('.sidebar-nav a');
    
    policySections.forEach(section => {
        section.classList.remove('active');
    });
    
    sidebarLinks.forEach(link => {
        link.classList.remove('active');
    });
    
    // Show first section by default
    const firstSection = document.getElementById('rfp-overview');
    const firstLink = document.querySelector('[data-section="rfp-overview"]');
    
    if (firstSection) firstSection.classList.add('active');
    if (firstLink) firstLink.classList.add('active');
}

// Show no results message
function showNoResults(query) {
    const contentArea = document.querySelector('.content-area');
    const noResultsDiv = document.createElement('div');
    noResultsDiv.className = 'no-results';
    noResultsDiv.innerHTML = `
        <div class="policy-section active">
            <div class="policy-header">
                <h2><i class="fas fa-search"></i> Search Results</h2>
            </div>
            <div class="policy-content">
                <div class="policy-card">
                    <h3>No results found</h3>
                    <p>Sorry, we couldn't find any policies matching "<strong>${escapeHtml(query)}</strong>".</p>
                    <p>Try searching with different keywords or browse the policy categories in the sidebar.</p>
                </div>
            </div>
        </div>
    `;
    
    // Remove existing no-results if any
    const existingNoResults = document.querySelector('.no-results');
    if (existingNoResults) {
        existingNoResults.remove();
    }
    
    contentArea.appendChild(noResultsDiv);
}

// Handle navigation clicks
function handleNavigation(href) {
    switch(href) {
        case '#rfp-process':
            // Already on RFP process page, scroll to top
            window.scrollTo({ top: 0, behavior: 'smooth' });
            break;
        case '#requirements':
            showSection('technical-requirements');
            break;
        case '#templates':
            showTemplatesPage();
            break;
        case '#support':
            showSupportPage();
            break;
    }
}

// Show specific section
function showSection(sectionId) {
    const section = document.getElementById(sectionId);
    const sidebarLink = document.querySelector(`[data-section="${sectionId}"]`);
    
    if (section) {
        // Hide all sections
        document.querySelectorAll('.policy-section').forEach(s => {
            s.classList.remove('active');
        });
        
        // Remove active from sidebar links
        document.querySelectorAll('.sidebar-nav a').forEach(l => {
            l.classList.remove('active');
        });
        
        // Show target section
        section.classList.add('active');
        
        if (sidebarLink) {
            sidebarLink.classList.add('active');
        }
        
        // Scroll to content
        document.querySelector('.content-area').scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    }
}

// Handle initial page load with hash
function handleInitialHash() {
    const hash = window.location.hash.substring(1);
    if (hash) {
        const section = document.getElementById(hash);
        const sidebarLink = document.querySelector(`[data-section="${hash}"]`);
        
        if (section && sidebarLink) {
            // Hide all sections
            document.querySelectorAll('.policy-section').forEach(s => {
                s.classList.remove('active');
            });
            
            // Remove active from sidebar links
            document.querySelectorAll('.sidebar-nav a').forEach(l => {
                l.classList.remove('active');
            });
            
            // Show target section
            section.classList.add('active');
            sidebarLink.classList.add('active');
        }
    } else {
        // Show default section
        showSection('rfp-overview');
    }
}

// Show templates page (placeholder)
function showTemplatesPage() {
    const contentArea = document.querySelector('.content-area');
    contentArea.innerHTML = `
        <div class="welcome-banner">
            <h2>RFP Templates & Documents</h2>
            <p>Download proposal templates and required documentation forms.</p>
        </div>
        <div class="policy-section active">
            <div class="policy-content">
                <div class="benefits-grid">
                    <div class="benefit-card">
                        <i class="fas fa-file-download"></i>
                        <h3>Proposal Template</h3>
                        <p>Download the official RFP response template with all required sections.</p>
                    </div>
                    <div class="benefit-card">
                        <i class="fas fa-file-contract"></i>
                        <h3>Technical Specifications</h3>
                        <p>Detailed technical requirements and system specifications document.</p>
                    </div>
                    <div class="benefit-card">
                        <i class="fas fa-calculator"></i>
                        <h3>Cost Breakdown Sheet</h3>
                        <p>Excel template for detailed project cost estimation and breakdown.</p>
                    </div>
                    <div class="benefit-card">
                        <i class="fas fa-question-circle"></i>
                        <h3>RFP FAQ</h3>
                        <p>Frequently asked questions about the RFP process and requirements.</p>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Show support page (placeholder)
function showSupportPage() {
    const contentArea = document.querySelector('.content-area');
    contentArea.innerHTML = `
        <div class="welcome-banner">
            <h2>RFP Support</h2>
            <p>Get assistance with your proposal submission and RFP questions.</p>
        </div>
        <div class="policy-section active">
            <div class="policy-content">
                <div class="policy-card">
                    <h3>Procurement Team</h3>
                    <p><strong>Email:</strong> procurement@company.com</p>
                    <p><strong>Phone:</strong> (555) 987-6543</p>
                    <p><strong>Office Hours:</strong> Monday - Friday, 8:00 AM - 6:00 PM</p>
                    <p><strong>Location:</strong> Building C, 3rd Floor, Procurement Office</p>
                </div>
                <div class="policy-card">
                    <h3>Technical Questions</h3>
                    <p><strong>Technical Lead:</strong> tech-rfp@company.com</p>
                    <p><strong>Response Time:</strong> Within 24 hours during business days</p>
                    <p>For technical clarifications and system requirements questions.</p>
                </div>
                <div class="policy-card">
                    <h3>Submission Support</h3>
                    <p><strong>Portal Help:</strong> rfp-support@company.com</p>
                    <p>For assistance with proposal submission and document upload issues.</p>
                </div>
            </div>
        </div>
    `;
}

// Responsive features
function setupResponsiveFeatures() {
    // Mobile menu toggle (if needed in future)
    const header = document.querySelector('.header');
    let lastScrollY = window.scrollY;
    
    window.addEventListener('scroll', () => {
        if (window.scrollY > lastScrollY && window.scrollY > 100) {
            header.style.transform = 'translateY(-100%)';
        } else {
            header.style.transform = 'translateY(0)';
        }
        lastScrollY = window.scrollY;
    });
}

// Utility functions
function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, function(m) { return map[m]; });
}

// Add CSS for search highlights
const style = document.createElement('style');
style.textContent = `
    .search-highlight {
        background-color: #fef3c7;
        color: #92400e;
        padding: 0.1rem 0.2rem;
        border-radius: 0.25rem;
        font-weight: 600;
    }
    
    .no-results {
        animation: fadeIn 0.5s ease-in;
    }
    
    @media (max-width: 768px) {
        .header {
            transition: transform 0.3s ease;
        }
    }
`;
document.head.appendChild(style);
