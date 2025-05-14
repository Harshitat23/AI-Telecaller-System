import re
import logging
import string
from difflib import get_close_matches

# Set up logging
logger = logging.getLogger(__name__)

# Knowledge base for real estate questions - Significantly expanded with common queries
REAL_ESTATE_KB = {
    # Buying questions - Expanded
    r"(buy|buying|purchase|purchasing).*house|home":
        "The home buying process typically involves getting pre-approved for a mortgage, finding a real estate agent, viewing properties, making an offer, conducting inspections, and closing the deal. We recommend starting with mortgage pre-approval to understand your budget. Our agents can guide you through each step of this process.",
    
    r"(mortgage|loan).*process|work|get|apply|qualify":
        "To get a mortgage, you'll need to apply with a lender, provide financial documentation like income verification and tax returns, undergo a credit check, and have the property appraised. Most mortgages are 15 or 30-year terms with fixed or adjustable rates. We recommend shopping around for the best interest rates and can connect you with trusted local lenders.",
    
    r"(down payment|downpayment)": 
        "Traditional mortgages typically require a 20% down payment, but there are many programs available for first-time buyers that allow down payments as low as 3-5%. FHA loans require just 3.5% down, and VA loans for veterans may require no down payment at all. Many states also offer down payment assistance programs for qualified buyers.",
    
    r"(first.time.buyer|first.time.home.buyer)": 
        "First-time homebuyers have access to special programs including FHA loans with low down payments, state-specific assistance programs, and possible tax credits. Many lenders offer specialized products for first-time buyers, and you may qualify for down payment assistance. Our team can connect you with resources specifically designed for first-time homebuyers.",
    
    r"(pre-approval|preapproval|pre approval)":
        "Mortgage pre-approval involves a lender reviewing your finances to determine how much you can borrow. This process typically requires documentation of income, assets, employment history, and a credit check. Getting pre-approved gives you a clear budget and shows sellers you're a serious buyer. We recommend getting pre-approved before starting your home search.",
    
    r"(house|home).*(inspection|inspector)":
        "A home inspection is a crucial step in the buying process where a professional examines the property's condition, including structural elements, electrical systems, plumbing, and more. The inspector will provide a detailed report of issues and recommended repairs. Inspections typically cost $300-600 and can help you negotiate repairs or price adjustments with the seller.",
    
    r"(closing|settlement).*(process|work)":
        "The closing process is the final step in a real estate transaction where ownership is transferred. It involves reviewing and signing documents, paying closing costs, and receiving keys to your new property. Typically, your real estate agent, attorney, and lender representatives will attend. The process usually takes 1-2 hours, and you'll need to bring identification and any required certified funds.",
    
    r"(earnest|good faith).*(money|deposit)":
        "Earnest money is a deposit made to show you're serious about buying a property. It's typically 1-3% of the purchase price and is held in escrow until closing, when it's applied to your down payment or closing costs. If you back out of the deal for reasons not covered in your contract contingencies, you may forfeit this deposit.",
    
    # Selling questions - Expanded
    r"(sell|selling).*house|home": 
        "To sell your home, you'll need to prepare it for listing, price it appropriately, market it effectively, negotiate offers, and handle closing procedures. Our agents can help with staging recommendations, professional photography, pricing strategy, and extensive marketing to maximize your sale price and streamline the process.",
    
    r"(house|home).*(worth|value)|property.*value|value.*property|home valuation": 
        "Property values are determined by factors including location, size, condition, comparable sales, and current market conditions. Recent improvements, school districts, and neighborhood amenities also impact value. We can provide a free, no-obligation comparative market analysis to give you an accurate estimate of your home's value in today's market.",
    
    r"(market|sell).*house|sell.*quickly|home selling tips": 
        "To market your house effectively, professional photography, virtual tours, broad online listing exposure, and staging are key strategies. Pricing correctly from the start is crucial. Our marketing approach includes professional photography and videography, virtual tours, targeted online ads, social media promotion, and leveraging our extensive buyer network to sell your home quickly and for top dollar.",
    
    r"(stage|staging).*(home|house)":
        "Home staging highlights your property's best features to make it more appealing to buyers. Effective staging includes decluttering, depersonalizing, cleaning thoroughly, making minor repairs, and arranging furniture to showcase space and flow. Professional staging typically costs $800-1200 but can increase your sale price by 5-10% and reduce time on market. Our agents can provide staging recommendations tailored to your property.",
    
    r"(sell).*(timeline|process|steps)":
        "The typical home selling process takes 2-3 months from listing to closing. Key steps include preparing your home, determining pricing, professional photography, listing on the market, hosting showings and open houses, reviewing offers, negotiating terms, home inspection, appraisal, and finally closing. Our team manages this timeline efficiently to make the process as smooth as possible.",
    
    r"(commission|realtor.*fee|agent.*fee)":
        "Real estate commission is typically 5-6% of the sale price, split between the listing and buyer's agents. This fee covers comprehensive marketing, professional photography, negotiation expertise, contract management, and guidance through the entire selling process. Commission is only paid when your home successfully sells, and the exact rate can be discussed during our listing consultation.",
    
    # Market questions - Expanded
    r"market.*(condition|trend|forecast|outlook)": 
        "The current real estate market shows moderate growth with inventory levels improving in most areas. Interest rates remain a key factor affecting buyer demand. Local markets vary significantly, with some neighborhoods seeing price increases while others stabilize. Our agents can provide detailed market analysis for specific areas you're interested in.",
    
    r"(interest rate|mortgage rate)": 
        "Current mortgage interest rates are fluctuating based on economic factors. Generally, rates for 30-year fixed mortgages have been competitive in recent months. Rate variations depend on loan type, credit score, and down payment amount. For the most up-to-date rates and personalized quotes, we recommend checking with lenders directly.",
    
    r"(investment|investing|property investment|rental property)": 
        "Real estate investments can include residential rentals, commercial properties, REITs, or fix-and-flip projects. Each strategy has different risk levels, returns, and management requirements. Rental properties typically provide both monthly income and long-term appreciation. The best approach depends on your financial goals, risk tolerance, and how active you want to be as an investor. Our team includes investment specialists who can help analyze potential returns.",
    
    r"(renting|rent).*(vs|versus|or).*(buying|buy)":
        "The rent vs. buy decision depends on your financial situation, stability needs, and long-term goals. Buying builds equity and provides tax benefits but requires upfront costs and maintenance responsibilities. Renting offers flexibility and fewer maintenance concerns but doesn't build equity. Generally, if you plan to stay in an area for at least 3-5 years, buying often makes financial sense. We can help analyze your specific situation.",
    
    r"(housing bubble|crash|correction)":
        "The current market shows little evidence of a housing bubble like 2008. Today's market is supported by stricter lending standards, low housing inventory, and genuine buyer demand rather than speculation. While some price moderation may occur with interest rate changes, most analysts don't anticipate a significant crash. Real estate remains a strong long-term investment, especially in growing areas.",
    
    # General questions - Expanded
    r"closing.*cost": 
        "Closing costs typically range from 2-5% of the loan amount and include fees for loan origination, appraisal, title insurance, attorney services, and taxes. Buyers usually pay more in closing costs than sellers, though some costs can be negotiated in the purchase agreement. Seller closing costs often include agent commissions, transfer taxes, and prorated property taxes.",
    
    r"(real estate agent|realtor)": 
        "A good real estate agent provides market expertise, negotiation skills, and guidance throughout the buying or selling process. They should have local knowledge, strong communication, and a track record of successful transactions. Our agents average over 10 years of experience and undergo continuous training to stay current with market trends and technology. We'd be happy to connect you with one of our experienced agents.",
    
    r"property tax|tax.*property": 
        "Property taxes vary by location and are typically based on the assessed value of your property. They fund local services like schools, police, fire protection, and infrastructure. Tax rates are set by local governments and can change annually. In some areas, there are exemptions available for primary residences, seniors, or veterans. We can provide information about property tax rates in specific areas you're interested in.",
    
    r"(homeowner.*insurance|insurance.*home)":
        "Homeowner's insurance covers damage to your property and liability for injuries occurring on your property. Typical policies cost $800-1500 annually depending on home value, location, and coverage levels. Lenders require insurance if you have a mortgage. Factors affecting rates include home age, construction materials, proximity to fire stations, and local disaster risks. We recommend getting quotes from multiple insurers.",
    
    r"(contingency|contingencies)":
        "Contingencies are conditions in a purchase agreement that must be met for the deal to proceed. Common contingencies include financing (ensuring you can get a mortgage), appraisal (property must value at or above purchase price), inspection (right to negotiate repairs), and home sale (buyer must sell their current home). These protect buyers from losing earnest money if specific conditions aren't met.",
    
    r"(hoa|homeowners association)":
        "Homeowners Associations (HOAs) govern shared communities like condos and planned developments. They enforce community rules, maintain common areas, and collect regular dues from homeowners. Monthly fees typically range from $100-500 depending on amenities and services provided. Before buying in an HOA community, review their financial health, rules, and restrictions to ensure they align with your lifestyle.",
    
    # Mortgages and Financing - Expanded
    r"(adjustable|arm|variable).*(rate|mortgage)":
        "Adjustable-rate mortgages (ARMs) offer lower initial interest rates that adjust periodically based on market indexes. Typical ARMs are described as 5/1 or 7/1, meaning they're fixed for 5 or 7 years before adjusting annually. ARMs can save money if you plan to move before the fixed period ends but carry risk if rates rise significantly. They often work well for short-term homeownership or in high-interest environments.",
    
    r"(fha|va|usda).*(loan|mortgage)":
        "Government-backed loans offer alternatives to conventional mortgages. FHA loans allow down payments as low as 3.5% with lower credit score requirements. VA loans for veterans offer no down payment and competitive rates. USDA loans support rural homebuyers with limited financing options. Each program has specific qualification requirements and different mortgage insurance considerations.",
    
    r"(pmi|private mortgage insurance)":
        "Private Mortgage Insurance (PMI) is required when you put less than 20% down on a conventional loan. It protects the lender if you default and typically costs 0.5-1.5% of the loan amount annually. PMI can be removed once you reach 20% equity through payments or home appreciation. Government-backed loans like FHA have their own mortgage insurance requirements that may last the life of the loan.",
    
    r"(refinance|refinancing)":
        "Refinancing replaces your current mortgage with a new loan, typically to secure a lower interest rate, reduce monthly payments, shorten loan terms, or access home equity. The process is similar to getting your original mortgage, requiring application, documentation, appraisal, and closing costs. Generally, refinancing makes financial sense if you can reduce your rate by at least 0.75-1% and plan to stay in your home long enough to recoup closing costs.",
    
    r"(credit score|fico).*mortgage":
        "Credit scores significantly impact mortgage approval and interest rates. Conventional loans typically require scores of at least 620, with the best rates reserved for scores above 740. FHA loans accept scores as low as 580 with 3.5% down, or 500 with 10% down. Your credit score can affect your interest rate by 0.5-1%, potentially changing your payment by hundreds of dollars monthly. We can recommend lenders who work with various credit profiles.",
    
    # New Construction and Home Types
    r"(new construction|new build|building).*home":
        "Buying new construction offers modern designs, customization options, and fewer maintenance concerns, but typically at premium prices. The process involves selecting a builder, choosing a lot and floor plan, making design selections, and multiple construction inspections. Timelines typically run 6-12 months. Having your own real estate agent represent you with builders can help negotiate upgrades, contingencies, and ensure quality standards.",
    
    r"(condo|condominium|townhouse|townhome)":
        "Condos and townhomes offer homeownership with typically lower prices and maintenance responsibilities than single-family homes. Condos have shared walls and common spaces with monthly HOA fees covering exterior maintenance and amenities. Financing can be more challenging with condos, requiring FHA or conventional approval of the entire complex. These properties often appeal to first-time buyers, downsizers, or investors.",
    
    r"(luxury|high.end|premium).*(home|property)":
        "Luxury real estate typically represents the top 10% of any market and offers premium features, locations, and materials. These properties require specialized marketing to reach qualified buyers and often take longer to sell than mid-range homes. Our luxury division provides enhanced photography, video tours, international marketing, and private showings to qualified buyers. We understand the discretion often required in luxury transactions.",
    
    # Company specific - Expanded
    r"premier.*service|service.*premier|your company": 
        "Premier Real Estate Services offers comprehensive support for buying, selling, and investing in properties. Our team of experienced agents provides personalized service, market expertise, and proven strategies to help you achieve your real estate goals. We combine cutting-edge technology with personalized attention to ensure exceptional client experiences.",
    
    r"work.*with.*premier|choose.*premier":
        "Working with Premier Real Estate Services gives you access to experienced agents averaging over 10 years in the business, comprehensive market knowledge, advanced marketing technology, and a client-focused approach. Our agents undergo continuous training to stay current with market trends and technology. We pride ourselves on communication, integrity, and results, with over 90% of our business coming from referrals and repeat clients.",
    
    # Advanced Real Estate Topics
    r"(1031|like.kind).*(exchange|swap)":
        "A 1031 exchange allows real estate investors to defer capital gains taxes by reinvesting proceeds from a property sale into a similar investment property. To qualify, you must identify replacement property within 45 days of selling and complete the purchase within 180 days. This strategy works well for investors looking to upgrade properties or diversify their portfolio without immediate tax consequences. We have specialists who can guide you through this process.",
    
    r"(off.market|pocket).*(listing|sale)":
        "Off-market or pocket listings are properties sold without being publicly listed on the MLS. These private sales can benefit sellers desiring privacy or testing a price point. For buyers, they offer opportunities with less competition. Our extensive agent network gives us access to off-market opportunities that aren't available to the general public. Let us know if you're interested in exploring these exclusive properties.",
    
    r"(short sale|foreclosure|reo|bank owned)":
        "Distressed properties like foreclosures and short sales can offer value but come with complications. Foreclosures are bank-owned properties sold as-is, often requiring significant repairs. Short sales occur when owners sell for less than they owe with lender approval, typically taking 3-6 months to close. While these properties may sell at 10-30% below market value, they require patience, flexibility, and often cash for repairs.",
    
    r"(commercial|retail|office|industrial).*(property|real estate)":
        "Commercial real estate involves different considerations than residential, including lease terms, tenant quality, income analysis, and zoning regulations. Returns typically range from 5-12% depending on property type and location. Investment categories include retail, office, industrial, and multi-family, each with unique risk profiles. Our commercial division can help evaluate potential investments or find suitable business locations.",
    
    # Additional Common Questions
    r"(seller|buyer).*(market|advantage)":
        "Market conditions favor either buyers or sellers depending on inventory levels, demand, and interest rates. In a seller's market, limited inventory gives sellers pricing power and often leads to multiple offers. In a buyer's market, excess inventory allows for more negotiation and concessions. Currently, most areas are seeing a more balanced market with slight advantages to sellers in desirable neighborhoods. Our agents can advise on specific local conditions.",
    
    r"(appraisal|appraiser)":
        "A home appraisal is an independent valuation of a property conducted by a licensed appraiser, typically required by lenders before approving a mortgage. The appraiser examines the home's condition, size, features, and comparable sales to determine market value. If an appraisal comes in below the purchase price, buyers may need to renegotiate, increase their down payment, or challenge the appraisal with additional data.",
    
    r"(home warranty|warranty)":
        "Home warranties cover repair or replacement of major home systems and appliances, typically costing $300-600 annually plus service call fees of $75-125. They provide budget protection for unexpected repairs but don't cover known pre-existing conditions or improper maintenance. Warranties are often included by sellers as a buyer incentive and can be especially valuable for first-time buyers or older homes.",
    
    r"(bidding war|multiple offer|offer strategy)":
        "In competitive markets, multiple offers or bidding wars require strategic approaches. Effective strategies include getting pre-approved, offering clean contracts with minimal contingencies, flexible closing dates, personalized offer letters, and sometimes escalation clauses that automatically increase your bid to a predetermined limit. Our agents are skilled negotiators who can help position your offer to stand out in competitive situations.",
}

# Category mapping for fallback responses if no exact match is found
CATEGORY_FALLBACKS = {
    "buying": "When buying a property, key considerations include your budget, location preferences, must-have features, and long-term plans. Getting pre-approved for a mortgage is an essential first step to understand your budget. Our agents can guide you through the entire process from property search to closing. What specific aspect of home buying are you interested in?",
    
    "selling": "Selling a home involves preparing your property, setting the right price, effective marketing, and negotiating offers. Our comprehensive approach includes professional photography, strategic pricing, broad online exposure, and skilled negotiation to maximize your return. Would you like specific information about any part of the selling process?",
    
    "financing": "Real estate financing involves understanding loan types, interest rates, credit requirements, and down payment options. Conventional loans typically require better credit and higher down payments, while government-backed loans like FHA offer more flexibility. Working with a trusted lender to get pre-approved is an important first step. What specific financing questions do you have?",
    
    "investment": "Real estate investing can provide both rental income and property appreciation. Common strategies include residential rentals, commercial properties, fix-and-flip projects, and REITs for passive investment. The best approach depends on your financial goals, risk tolerance, and desired level of involvement. How are you considering investing in real estate?",
    
    "market": "Real estate markets are localized, with conditions varying by neighborhood. Current trends show stabilizing prices with moderate growth in most areas, though inventory levels and interest rates continue to impact buyer demand. Our local market expertise can help you understand conditions in specific areas you're interested in. Which location are you curious about?",
    
    "property": "Properties vary widely in type, from single-family homes to condos, townhomes, and multi-family units. Each offers different advantages in terms of space, maintenance, amenities, and investment potential. Understanding your lifestyle needs and long-term goals helps determine the best property type for you. What features are most important to you in a property?",
}

# Keywords for category identification
CATEGORY_KEYWORDS = {
    "buying": ["buy", "buying", "purchase", "offer", "closing", "inspection", "escrow", "first-time", "house hunting"],
    "selling": ["sell", "selling", "list", "market", "stage", "price", "value", "worth", "commission", "agent"],
    "financing": ["mortgage", "loan", "interest", "rate", "down payment", "pre-approval", "credit", "financing", "lender", "pmi"],
    "investment": ["invest", "investment", "rental", "income", "roi", "cash flow", "appreciation", "passive", "portfolio"],
    "market": ["market", "trend", "forecast", "appreciation", "depreciation", "bubble", "crash", "inventory", "demand"],
    "property": ["property", "home", "house", "condo", "townhouse", "land", "acre", "square foot", "bedroom", "bathroom"]
}

def preprocess_query(query):
    """Clean and normalize the query for better matching"""
    if not query:
        return ""
        
    # Convert to lowercase
    query = query.lower().strip()
    
    # Remove punctuation
    translator = str.maketrans('', '', string.punctuation)
    query = query.translate(translator)
    
    return query

def identify_category(query):
    """Identify which real estate category the query belongs to"""
    preprocessed = preprocess_query(query)
    
    # Count keyword matches for each category
    category_scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in preprocessed)
        category_scores[category] = score
    
    # Return the category with the highest score, or None if no matches
    max_category = max(category_scores.items(), key=lambda x: x[1])
    if max_category[1] > 0:
        return max_category[0]
    return None

def get_response(query):
    """
    Check if the query matches any patterns in our knowledge base
    Returns: (response_text, found_match)
    """
    try:
        if not query:
            logger.warning("Empty query received")
            return None, False
            
        # Normalize the query
        normalized_query = preprocess_query(query)
        
        # Log the query we're trying to match
        logger.debug(f"Attempting to match query: '{normalized_query}'")
        
        # Search for matching patterns
        for pattern, response in REAL_ESTATE_KB.items():
            # Check for a match with regex
            if re.search(pattern, normalized_query, re.IGNORECASE):
                logger.info(f"Found knowledge base match with pattern: {pattern}")
                return response, True
        
        # If no regex match, try fuzzy matching with the patterns
        pattern_strings = [p.replace(r'.*', ' ').replace('|', ' ').replace('(', '').replace(')', '') 
                          for p in REAL_ESTATE_KB.keys()]
        
        # Simplify patterns for better matching
        simplified_patterns = []
        for p in pattern_strings:
            # Extract main keywords
            words = p.split()
            keywords = [w for w in words if len(w) > 3]  # Only keep significant words
            if keywords:
                simplified_patterns.append(' '.join(keywords))
        
        # Try to find close matches
        query_parts = normalized_query.split()
        for q_part in query_parts:
            if len(q_part) > 3:  # Only consider significant words
                matches = get_close_matches(q_part, simplified_patterns, n=1, cutoff=0.8)
                if matches:
                    logger.info(f"Found fuzzy match: {matches[0]} for query part: {q_part}")
                    # Find the original pattern that corresponds to this match
                    for pattern, response in REAL_ESTATE_KB.items():
                        if matches[0] in pattern.replace(r'.*', ' ').replace('|', ' ').replace('(', '').replace(')', ''):
                            return response, True
        
        # If still no match, see if we can categorize the query
        category = identify_category(normalized_query)
        if category and category in CATEGORY_FALLBACKS:
            logger.info(f"Using category fallback for: {category}")
            return CATEGORY_FALLBACKS[category], True
        
        # If no match was found
        logger.info("No knowledge base match found")
        return None, False
    except Exception as e:
        logger.error(f"Error in knowledge base lookup: {str(e)}")
        return None, False