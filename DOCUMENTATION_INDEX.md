# Documentation Index

This guide explains which documentation file to use for different purposes.

## 📚 Main Documentation Files

### 1. **README.md** - Start Here!
**Purpose:** Main project overview and quick start guide  
**Use when:**
- First time setting up the project
- Need installation instructions
- Want to understand project structure
- Looking for basic usage examples

**Contains:**
- Project overview and features
- Installation instructions
- Basic usage examples
- API endpoint overview
- Configuration guide

---

### 2. **USAGE_GUIDE.md** - API Usage
**Purpose:** Detailed guide for using the API endpoints  
**Use when:**
- Working with the REST API
- Testing endpoints via Swagger UI
- Understanding what works with/without API keys
- Need examples for specific API calls

**Contains:**
- Step-by-step API usage
- Endpoint examples with curl commands
- Configuration levels (demo vs. real trading)
- Swagger UI testing guide
- Common issues and solutions

---

### 3. **EXCHANGES.md** - Exchange Configuration
**Purpose:** Exchange-specific information and setup  
**Use when:**
- Setting up exchange API credentials
- Understanding symbol formats
- Need exchange-specific details
- Troubleshooting exchange connections

**Contains:**
- All 5 supported exchanges (Nobitex, Wallex, KuCoin, Invex, Tabdeal)
- API credential setup for each exchange
- Symbol format conversion rules
- Fee structures (updated with real values)
- Authentication methods
- Error handling information

---

### 4. **TESTING_GUIDE.md** - Testing Instructions
**Purpose:** How to test the bot functionality  
**Use when:**
- Running tests before presentation
- Testing with mock data
- Testing with real API data
- Understanding test categories

**Contains:**
- Test script usage (`test_bot.py`)
- Different test modes (realistic, paper, dry-run)
- What gets tested with/without authentication
- Expected results
- Troubleshooting test issues

---

### 5. **PRESENTATION_CHECKLIST.md** - Presentation Prep
**Purpose:** Checklist for jury presentation  
**Use when:**
- Preparing for presentation
- Need to verify everything works
- Want presentation flow guidance
- Need answers to common questions

**Contains:**
- Pre-presentation verification steps
- Presentation flow and timing
- Live demonstration steps
- Common Q&A
- Troubleshooting during presentation
- Success criteria

---

### 6. **ROADMAP.md** - Development Plan
**Purpose:** Project development roadmap and status  
**Use when:**
- Understanding project progress
- Planning future features
- Checking what's completed
- Understanding project phases

**Contains:**
- All development phases
- Completed features (✅)
- In-progress features (🔄)
- Planned features (📋)
- Key metrics to track

---

## 📁 Technical Documentation (docs/)

### 7. **docs/BOT_ARCHITECTURE.md** - System Architecture
**Purpose:** Technical deep-dive into bot architecture  
**Use when:**
- Understanding how the bot works internally
- Need to know about order tracking
- Understanding exchange switching
- Planning modifications

**Contains:**
- Bot startup sequence
- Order tracking implementation
- Exchange switching mechanism
- Database considerations
- Fee configuration details

---

### 8. **docs/ORDER_TRACKING.md** - Order Management
**Purpose:** Detailed explanation of order tracking  
**Use when:**
- Understanding how orders are tracked
- Need to know about persistence
- Planning production deployment
- Understanding limitations

**Contains:**
- In-memory vs. database tracking
- Order recovery strategies
- Production recommendations
- Current limitations

---

## 🎯 Quick Reference Guide

### "I want to..."

**...set up the project for the first time**
→ Read **README.md** (Installation section)

**...use the API endpoints**
→ Read **USAGE_GUIDE.md**

**...configure exchange API keys**
→ Read **EXCHANGES.md**

**...test the bot functionality**
→ Read **TESTING_GUIDE.md** and run `python test_bot.py --mode realistic`

**...prepare for presentation**
→ Read **PRESENTATION_CHECKLIST.md**

**...understand how the bot works internally**
→ Read **docs/BOT_ARCHITECTURE.md**

**...understand order tracking and persistence**
→ Read **docs/ORDER_TRACKING.md**

**...see project progress and future plans**
→ Read **ROADMAP.md**

---

## 📝 File Update Status

All documentation files have been updated as of the latest changes:

- ✅ **README.md** - Up to date
- ✅ **USAGE_GUIDE.md** - Up to date
- ✅ **EXCHANGES.md** - Updated with correct fee amounts and symbol conversion info
- ✅ **TESTING_GUIDE.md** - Updated to reference `test_bot.py` instead of deleted files
- ✅ **PRESENTATION_CHECKLIST.md** - Updated to reference `test_bot.py`
- ✅ **ROADMAP.md** - Up to date with Phase 3 completion
- ✅ **docs/BOT_ARCHITECTURE.md** - Up to date
- ✅ **docs/ORDER_TRACKING.md** - Up to date

---

## 🔍 Finding Information

**Need information about...**

- **Installation?** → README.md
- **API usage?** → USAGE_GUIDE.md
- **Exchange setup?** → EXCHANGES.md
- **Testing?** → TESTING_GUIDE.md
- **Presentation?** → PRESENTATION_CHECKLIST.md
- **Architecture?** → docs/BOT_ARCHITECTURE.md
- **Order tracking?** → docs/ORDER_TRACKING.md
- **Project status?** → ROADMAP.md

---

## 💡 Tips

1. **Start with README.md** - It provides the foundation
2. **Use USAGE_GUIDE.md** for API work
3. **Check EXCHANGES.md** before configuring exchanges
4. **Follow PRESENTATION_CHECKLIST.md** before your presentation
5. **Read technical docs** when you need deep understanding

All documentation is kept up-to-date with the current codebase!

