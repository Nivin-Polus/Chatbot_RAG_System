# app/services/crawler/structured_data_extractor.py
"""
Structured Data Extractor - Phase 1

Extracts structured data from HTML pages including:
- JSON-LD (schema.org markup in <script type="application/ld+json">)
- Microdata (itemscope, itemtype, itemprop attributes)
- OpenGraph metadata (og: meta tags)

Features:
- Confidence scoring for all extracted data
- Explicit @graph handling for JSON-LD
- Filtered microdata extraction (Person, Organization, BlogPosting, Employee only)
- Social link normalization
- Graceful error handling for malformed data
"""

import json
import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger("structured_data_extractor")


# =============================================================================
# CONSTANTS
# =============================================================================

# Confidence scores by source
CONFIDENCE_JSON_LD = 0.95
CONFIDENCE_MICRODATA = 0.85
CONFIDENCE_OPENGRAPH = 0.80

# Allowed microdata types (Phase 1 - limited scope to reduce noise)
ALLOWED_MICRODATA_TYPES = [
    "https://schema.org/Person",
    "http://schema.org/Person",
    "https://schema.org/Organization",
    "http://schema.org/Organization",
    "https://schema.org/BlogPosting",
    "http://schema.org/BlogPosting",
    "https://schema.org/Employee",
    "http://schema.org/Employee",
    "https://schema.org/Article",
    "http://schema.org/Article",
]

# Social platform normalization map
SOCIAL_PLATFORM_MAP = {
    # LinkedIn
    "linkedin.com": "linkedin",
    "www.linkedin.com": "linkedin",
    
    # Twitter/X
    "twitter.com": "twitter",
    "www.twitter.com": "twitter",
    "x.com": "twitter",
    "www.x.com": "twitter",
    
    # GitHub
    "github.com": "github",
    "www.github.com": "github",
    
    # Facebook
    "facebook.com": "facebook",
    "www.facebook.com": "facebook",
    "fb.com": "facebook",
    "www.fb.com": "facebook",
    
    # Instagram
    "instagram.com": "instagram",
    "www.instagram.com": "instagram",
    
    # YouTube
    "youtube.com": "youtube",
    "www.youtube.com": "youtube",
    
    # Other platforms
    "medium.com": "medium",
    "www.medium.com": "medium",
    "dribbble.com": "dribbble",
    "www.dribbble.com": "dribbble",
    "behance.net": "behance",
    "www.behance.net": "behance",
}

# Person schema fields to extract
PERSON_FIELDS = [
    "name", "givenName", "familyName", "jobTitle", "description",
    "image", "url", "sameAs", "email", "telephone", "worksFor",
    "alumniOf", "awards", "knowsAbout", "address", "birthDate",
    "nationality", "affiliation", "brand", "colleague", "contactPoint"
]

# Organization schema fields to extract
ORGANIZATION_FIELDS = [
    "name", "legalName", "description", "url", "logo", "image",
    "address", "telephone", "email", "sameAs", "founder", "employee",
    "numberOfEmployees", "foundingDate", "areaServed"
]


# =============================================================================
# STRUCTURED DATA EXTRACTOR
# =============================================================================

class StructuredDataExtractor:
    """
    Extracts structured data from HTML pages.
    
    Supports:
    - JSON-LD with @graph handling
    - Microdata (filtered to allowed types)
    - OpenGraph metadata
    
    All extracted data includes confidence scores.
    """
    
    def __init__(self):
        """Initialize the extractor."""
        pass
    
    # -------------------------------------------------------------------------
    # MAIN EXTRACTION METHOD
    # -------------------------------------------------------------------------
    
    def extract(self, soup: BeautifulSoup, url: str) -> Optional[Dict]:
        """
        Extract all structured data from a page.
        
        Args:
            soup: BeautifulSoup parsed HTML
            url: The page URL
            
        Returns:
            Dictionary with extracted data:
            {
                "json_ld": [...],
                "microdata": [...],
                "opengraph": {...},
                "persons": [...],
                "organizations": [...],
            }
            or None if no structured data found
        """
        try:
            # Extract from all sources
            json_ld_data = self._extract_json_ld(soup)
            microdata = self._extract_microdata(soup)
            opengraph = self._extract_opengraph(soup)
            
            # Check if we found anything
            has_data = (
                len(json_ld_data) > 0 or
                len(microdata) > 0 or
                (opengraph and len(opengraph) > 1)  # More than just confidence
            )
            
            if not has_data:
                return None
            
            # Extract and normalize Person/Organization entities
            persons = self._extract_persons_from_schemas(json_ld_data, microdata, url)
            organizations = self._extract_organizations_from_schemas(json_ld_data, microdata, url)
            
            return {
                "json_ld": json_ld_data,
                "microdata": microdata,
                "opengraph": opengraph,
                "persons": persons,
                "organizations": organizations,
            }
            
        except Exception as e:
            logger.error(f"Error extracting structured data from {url}: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # JSON-LD EXTRACTION
    # -------------------------------------------------------------------------
    
    def _extract_json_ld(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Extract all JSON-LD blocks from the page.
        
        Handles:
        - Multiple <script type="application/ld+json"> blocks
        - Nested @graph structures
        - Malformed JSON (logs warning, skips block)
        
        Args:
            soup: BeautifulSoup parsed HTML
            
        Returns:
            List of JSON-LD objects with confidence scores
        """
        results = []
        
        # Find all JSON-LD script tags
        json_ld_scripts = soup.find_all("script", type="application/ld+json")
        
        for script in json_ld_scripts:
            try:
                # Get script content
                content = script.string
                if not content:
                    continue
                
                # Clean the content (remove CDATA, comments)
                content = content.strip()
                if content.startswith("//<![CDATA["):
                    content = content[11:]
                if content.endswith("//]]>"):
                    content = content[:-5]
                content = content.strip()
                
                # Parse JSON
                try:
                    data = json.loads(content)
                except json.JSONDecodeError as e:
                    logger.warning(f"Malformed JSON-LD block: {e}")
                    continue
                
                # Flatten @graph structures
                flattened = self._flatten_json_ld(data)
                
                for entity in flattened:
                    results.append({
                        "data": entity,
                        "confidence": CONFIDENCE_JSON_LD
                    })
                    
            except Exception as e:
                logger.warning(f"Error processing JSON-LD block: {e}")
                continue
        
        return results
    
    def _flatten_json_ld(self, data: Any) -> List[Dict]:
        """
        Flatten JSON-LD structures including @graph.
        
        Handles:
        - Single object: {"@type": "Person", ...}
        - Array: [{"@type": "Person"}, {"@type": "Organization"}]
        - Graph: {"@graph": [{"@type": "Person"}, ...]}
        - Nested graphs
        
        Args:
            data: JSON-LD data (dict, list, or other)
            
        Returns:
            List of individual entity dictionaries
        """
        entities = []
        
        if isinstance(data, list):
            for item in data:
                entities.extend(self._flatten_json_ld(item))
        elif isinstance(data, dict):
            # Check for @graph
            if "@graph" in data:
                entities.extend(self._flatten_json_ld(data["@graph"]))
                # Also include the parent if it has a type
                if "@type" in data:
                    parent = {k: v for k, v in data.items() if k != "@graph"}
                    entities.append(parent)
            else:
                entities.append(data)
        
        return entities
    
    # -------------------------------------------------------------------------
    # MICRODATA EXTRACTION
    # -------------------------------------------------------------------------
    
    def _extract_microdata(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Extract Microdata from the page.
        
        Limited to allowed types to prevent noise:
        - schema.org/Person
        - schema.org/Organization
        - schema.org/BlogPosting
        - schema.org/Employee
        
        Args:
            soup: BeautifulSoup parsed HTML
            
        Returns:
            List of microdata items with confidence scores
        """
        results = []
        
        # Find all elements with itemscope
        itemscope_elements = soup.find_all(attrs={"itemscope": True})
        
        for element in itemscope_elements:
            try:
                # Get itemtype
                itemtype = element.get("itemtype", "")
                
                # Filter to allowed types only
                if itemtype not in ALLOWED_MICRODATA_TYPES:
                    continue
                
                # Extract properties
                properties = self._extract_microdata_properties(element)
                
                if properties:
                    results.append({
                        "data": {
                            "type": itemtype,
                            "properties": properties
                        },
                        "confidence": CONFIDENCE_MICRODATA
                    })
                    
            except Exception as e:
                logger.warning(f"Error extracting microdata item: {e}")
                continue
        
        return results
    
    def _extract_microdata_properties(self, element: Tag) -> Dict:
        """
        Extract all itemprop values from a microdata item.
        
        Args:
            element: The itemscope element
            
        Returns:
            Dictionary of property name -> value
        """
        properties = {}
        
        # Find all itemprop elements within this scope
        # but not within nested itemscopes
        def get_direct_itemprops(el: Tag) -> List[Tag]:
            """Get itemprop elements that belong to this scope."""
            result = []
            for child in el.find_all(attrs={"itemprop": True}):
                # Check if this itemprop belongs to a nested scope
                parent_scope = child.find_parent(attrs={"itemscope": True})
                if parent_scope == el:
                    result.append(child)
            return result
        
        for prop_element in get_direct_itemprops(element):
            prop_name = prop_element.get("itemprop", "")
            if not prop_name:
                continue
            
            # Get value based on element type
            value = self._get_microdata_value(prop_element)
            
            if value:
                # Handle multiple values for same property
                if prop_name in properties:
                    existing = properties[prop_name]
                    if isinstance(existing, list):
                        existing.append(value)
                    else:
                        properties[prop_name] = [existing, value]
                else:
                    properties[prop_name] = value
        
        return properties
    
    def _get_microdata_value(self, element: Tag) -> Optional[str]:
        """
        Get the value of a microdata property element.
        
        Value extraction rules:
        - meta: content attribute
        - link/a: href attribute
        - img: src attribute
        - time: datetime attribute
        - others: text content
        
        Args:
            element: The itemprop element
            
        Returns:
            The property value or None
        """
        tag_name = element.name.lower() if element.name else ""
        
        if tag_name == "meta":
            return element.get("content")
        elif tag_name in ("link", "a"):
            return element.get("href")
        elif tag_name == "img":
            return element.get("src")
        elif tag_name == "time":
            return element.get("datetime") or element.get_text(strip=True)
        elif tag_name == "data":
            return element.get("value")
        else:
            return element.get_text(strip=True)
    
    # -------------------------------------------------------------------------
    # OPENGRAPH EXTRACTION
    # -------------------------------------------------------------------------
    
    def _extract_opengraph(self, soup: BeautifulSoup) -> Optional[Dict]:
        """
        Extract OpenGraph metadata from the page.
        
        Extracts og: prefixed meta tags.
        
        Args:
            soup: BeautifulSoup parsed HTML
            
        Returns:
            Dictionary of og properties with confidence, or None if not found
        """
        og_data = {}
        
        # Find all og: meta tags
        for meta in soup.find_all("meta"):
            property_attr = meta.get("property", "")
            if property_attr.startswith("og:"):
                content = meta.get("content", "")
                if content:
                    og_data[property_attr] = content
        
        if not og_data:
            return None
        
        og_data["confidence"] = CONFIDENCE_OPENGRAPH
        return og_data
    
    # -------------------------------------------------------------------------
    # PERSON EXTRACTION FROM SCHEMAS
    # -------------------------------------------------------------------------
    
    def _extract_persons_from_schemas(
        self, 
        json_ld_data: List[Dict], 
        microdata: List[Dict],
        url: str
    ) -> List[Dict]:
        """
        Extract and normalize Person entities from structured data.
        
        Args:
            json_ld_data: Extracted JSON-LD data
            microdata: Extracted microdata
            url: Page URL
            
        Returns:
            List of normalized person dictionaries
        """
        persons = []
        
        # Extract from JSON-LD
        for item in json_ld_data:
            data = item.get("data", {})
            entity_type = data.get("@type", "")
            
            # Handle array of types
            if isinstance(entity_type, list):
                entity_type = entity_type[0] if entity_type else ""
            
            if entity_type in ("Person", "Employee"):
                person = self._normalize_person(
                    data, 
                    source="json_ld", 
                    confidence=item.get("confidence", CONFIDENCE_JSON_LD),
                    url=url
                )
                if person:
                    persons.append(person)
        
        # Extract from Microdata
        for item in microdata:
            data = item.get("data", {})
            item_type = data.get("type", "")
            
            if "Person" in item_type or "Employee" in item_type:
                properties = data.get("properties", {})
                person = self._normalize_person(
                    properties,
                    source="microdata",
                    confidence=item.get("confidence", CONFIDENCE_MICRODATA),
                    url=url
                )
                if person:
                    persons.append(person)
        
        return persons
    
    def _normalize_person(
        self, 
        data: Dict, 
        source: str, 
        confidence: float,
        url: str
    ) -> Optional[Dict]:
        """
        Normalize a person entity to standard format.
        
        Args:
            data: Raw person data
            source: Data source ("json_ld" or "microdata")
            confidence: Confidence score
            url: Source page URL
            
        Returns:
            Normalized person dictionary or None if invalid
        """
        # Extract name (required field)
        name = self._extract_nested_value(data, ["name", "givenName", "familyName"])
        if not name:
            return None
        
        # If we got givenName/familyName, combine them
        if "givenName" in data or "familyName" in data:
            given = data.get("givenName", "")
            family = data.get("familyName", "")
            if given or family:
                name = f"{given} {family}".strip()
        
        # Extract job title
        title = self._extract_nested_value(data, ["jobTitle", "roleName", "title"])
        
        # Extract description
        description = self._extract_nested_value(data, ["description", "bio", "about"])
        
        # Extract image URL
        image_url = self._extract_image_url(data)
        
        # Extract social links
        social_links = self._extract_social_links(data)
        
        # Extract email
        email = self._extract_email(data)
        
        # Extract worksFor (organization)
        works_for = self._extract_works_for(data)
        
        # Extract alumni of
        alumni_of = self._extract_nested_value(data, ["alumniOf"])
        if isinstance(alumni_of, dict):
            alumni_of = alumni_of.get("name", str(alumni_of))
        
        # Extract awards
        awards = data.get("awards", [])
        if isinstance(awards, str):
            awards = [awards]
        
        # Extract knows about
        knows_about = data.get("knowsAbout", [])
        if isinstance(knows_about, str):
            knows_about = [knows_about]
        
        return {
            "name": name,
            "title": title,
            "description": description,
            "image_url": image_url,
            "image_alt": None,  # Not typically in structured data
            "social_links": social_links,
            "email": email,
            "telephone": data.get("telephone"),
            "department": None,  # Not typically in structured data
            "works_for": works_for,
            "alumni_of": alumni_of,
            "awards": awards if awards else None,
            "knows_about": knows_about if knows_about else None,
            "confidence": confidence,
            "extraction_method": "structured_data",
            "source": source,
            "source_urls": [url]
        }
    
    # -------------------------------------------------------------------------
    # ORGANIZATION EXTRACTION FROM SCHEMAS
    # -------------------------------------------------------------------------
    
    def _extract_organizations_from_schemas(
        self, 
        json_ld_data: List[Dict], 
        microdata: List[Dict],
        url: str
    ) -> List[Dict]:
        """
        Extract and normalize Organization entities from structured data.
        
        Args:
            json_ld_data: Extracted JSON-LD data
            microdata: Extracted microdata
            url: Page URL
            
        Returns:
            List of normalized organization dictionaries
        """
        organizations = []
        
        # Extract from JSON-LD
        for item in json_ld_data:
            data = item.get("data", {})
            entity_type = data.get("@type", "")
            
            if isinstance(entity_type, list):
                entity_type = entity_type[0] if entity_type else ""
            
            if entity_type in ("Organization", "Corporation", "Company", "LocalBusiness"):
                org = self._normalize_organization(
                    data,
                    source="json_ld",
                    confidence=item.get("confidence", CONFIDENCE_JSON_LD),
                    url=url
                )
                if org:
                    organizations.append(org)
        
        # Extract from Microdata
        for item in microdata:
            data = item.get("data", {})
            item_type = data.get("type", "")
            
            if "Organization" in item_type:
                properties = data.get("properties", {})
                org = self._normalize_organization(
                    properties,
                    source="microdata",
                    confidence=item.get("confidence", CONFIDENCE_MICRODATA),
                    url=url
                )
                if org:
                    organizations.append(org)
        
        return organizations
    
    def _normalize_organization(
        self, 
        data: Dict, 
        source: str, 
        confidence: float,
        url: str
    ) -> Optional[Dict]:
        """
        Normalize an organization entity to standard format.
        
        Args:
            data: Raw organization data
            source: Data source
            confidence: Confidence score
            url: Source page URL
            
        Returns:
            Normalized organization dictionary or None if invalid
        """
        name = self._extract_nested_value(data, ["name", "legalName"])
        if not name:
            return None
        
        # Extract logo/image
        logo = self._extract_image_url(data, ["logo", "image"])
        
        return {
            "name": name,
            "description": data.get("description"),
            "url": data.get("url"),
            "logo": logo,
            "address": self._extract_address(data),
            "telephone": data.get("telephone"),
            "email": self._extract_email(data),
            "social_links": self._extract_social_links(data),
            "founding_date": data.get("foundingDate"),
            "confidence": confidence,
            "source": source,
            "source_urls": [url]
        }
    
    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------
    
    def _extract_nested_value(self, data: Dict, keys: List[str]) -> Optional[str]:
        """
        Extract value from data trying multiple keys.
        
        Args:
            data: Source dictionary
            keys: List of keys to try in order
            
        Returns:
            First found value or None
        """
        for key in keys:
            value = data.get(key)
            if value:
                if isinstance(value, dict):
                    # Try to get name or value from nested dict
                    return value.get("name") or value.get("value") or value.get("@value")
                elif isinstance(value, list):
                    # Return first item if list
                    return value[0] if value else None
                else:
                    return str(value)
        return None
    
    def _extract_image_url(self, data: Dict, keys: List[str] = None) -> Optional[str]:
        """
        Extract image URL from data.
        
        Handles:
        - Direct URL string
        - {"@type": "ImageObject", "url": "..."}
        - {"contentUrl": "..."}
        
        Args:
            data: Source dictionary
            keys: Keys to check (defaults to ["image"])
            
        Returns:
            Image URL or None
        """
        if keys is None:
            keys = ["image"]
        
        for key in keys:
            value = data.get(key)
            if not value:
                continue
            
            if isinstance(value, str):
                return value
            elif isinstance(value, dict):
                return (
                    value.get("url") or 
                    value.get("contentUrl") or 
                    value.get("@id")
                )
            elif isinstance(value, list) and value:
                first = value[0]
                if isinstance(first, str):
                    return first
                elif isinstance(first, dict):
                    return first.get("url") or first.get("contentUrl")
        
        return None
    
    def _extract_social_links(self, data: Dict) -> Dict[str, str]:
        """
        Extract and normalize social media links.
        
        Uses sameAs property which typically contains social profiles.
        Normalizes platform names (x.com -> twitter, etc.)
        
        Args:
            data: Source dictionary
            
        Returns:
            Dictionary of platform -> URL
        """
        social_links = {}
        
        same_as = data.get("sameAs", [])
        if isinstance(same_as, str):
            same_as = [same_as]
        
        for url in same_as:
            if not isinstance(url, str):
                continue
            
            platform = self._normalize_social_platform(url)
            if platform:
                social_links[platform] = url
        
        # Also check for direct social properties
        url_value = data.get("url")
        if url_value and isinstance(url_value, str):
            platform = self._normalize_social_platform(url_value)
            if platform and platform not in social_links:
                social_links[platform] = url_value
        
        return social_links
    
    def _normalize_social_platform(self, url: str) -> Optional[str]:
        """
        Normalize a URL to a social platform name.
        
        Args:
            url: URL to normalize
            
        Returns:
            Platform name or None if not recognized
        """
        try:
            parsed = urlparse(url)
            hostname = parsed.netloc.lower()
            
            # Remove port if present
            if ":" in hostname:
                hostname = hostname.split(":")[0]
            
            return SOCIAL_PLATFORM_MAP.get(hostname)
        except Exception:
            return None
    
    def _extract_email(self, data: Dict) -> Optional[str]:
        """
        Extract email from data.
        
        Handles both direct email and mailto: links.
        
        Args:
            data: Source dictionary
            
        Returns:
            Email address or None
        """
        email = data.get("email")
        if email:
            if email.startswith("mailto:"):
                email = email[7:]
            return email
        return None
    
    def _extract_works_for(self, data: Dict) -> Optional[str]:
        """
        Extract organization name from worksFor.
        
        Args:
            data: Source dictionary
            
        Returns:
            Organization name or None
        """
        works_for = data.get("worksFor")
        if not works_for:
            return None
        
        if isinstance(works_for, str):
            return works_for
        elif isinstance(works_for, dict):
            return works_for.get("name") or works_for.get("legalName")
        elif isinstance(works_for, list) and works_for:
            first = works_for[0]
            if isinstance(first, str):
                return first
            elif isinstance(first, dict):
                return first.get("name")
        
        return None
    
    def _extract_address(self, data: Dict) -> Optional[Dict]:
        """
        Extract address from data.
        
        Args:
            data: Source dictionary
            
        Returns:
            Address dictionary or None
        """
        address = data.get("address")
        if not address:
            return None
        
        if isinstance(address, str):
            return {"formatted": address}
        elif isinstance(address, dict):
            return {
                "street": address.get("streetAddress"),
                "city": address.get("addressLocality"),
                "region": address.get("addressRegion"),
                "postal_code": address.get("postalCode"),
                "country": address.get("addressCountry"),
                "formatted": address.get("name") or address.get("@value")
            }
        
        return None
