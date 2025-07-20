# Enhanced mem-mcp Project Memory

## Project Overview
Enhanced MCP (Model Context Protocol) Memory Server - A sophisticated personal memory management system with rich metadata, temporal filtering, duplicate detection, and comprehensive search capabilities. Built following Uncle Bob's clean code principles for maintainability and extensibility.

## Key Features Implemented
- ✅ **Rich Temporal Metadata**: Automatic extraction of detailed time information (day, hour, quarter, weekends, etc.)
- ✅ **Duplicate Prevention**: 0.95 similarity threshold with configurable handling options
- ✅ **Enhanced Memory Storage**: Tags, people mentioned, topic categories with validation
- ✅ **Hybrid Search Engine**: Combine semantic similarity with metadata filtering
- ✅ **Natural Language Temporal Queries**: "yesterday", "weekends", "Q3", "morning", etc.
- ✅ **Comprehensive Filtering**: Search by tags, people, topics, time periods
- ✅ **Backward Compatibility**: Legacy tools remain unchanged

## Enhanced Project Structure

### Core Enhanced Files

#### `server.py`
- **Purpose**: Enhanced MCP server with 8 comprehensive tools
- **Enhanced Tools**:
  - `add_memory()`: Legacy tool (backward compatibility)
  - `retrieve_memory()`: Legacy tool (backward compatibility)
  - `add_memory_with_metadata()`: Enhanced memory addition with rich metadata
  - `search_memories_enhanced()`: Comprehensive search with all filters
  - `temporal_search()`: Time-based search with natural language queries
  - `search_by_tags()`: Tag-based filtering with semantic combination
  - `search_by_people()`: People-mentioned filtering
  - `search_by_topic()`: Topic category filtering
- **Dependencies**: Enhanced search engine, all utility modules
- **Notes**: Maintains backward compatibility while providing advanced capabilities

#### `add_memory_to_collection.py`
- **Purpose**: Enhanced memory storage with rich metadata and duplicate detection
- **Key Classes**:
  - `EnhancedMemoryManager`: Main class handling advanced memory operations
- **Key Functions**:
  - `add_memory_with_metadata()`: Core enhanced memory addition
  - `add_memory_enhanced()`: MCP-friendly wrapper function
  - `add_memory()`: Legacy function for backward compatibility
- **Important Features**:
  - Rich temporal metadata generation
  - Tags, people, and topic validation and cleaning
  - Duplicate detection integration
  - Comprehensive error handling
  - Formatted response messages with emojis

#### `src/shared/temporal_utils.py`
- **Purpose**: Rich temporal metadata processing and natural language parsing
- **Key Classes**:
  - `TemporalProcessor`: Generates detailed temporal metadata from timestamps
  - `TemporalFilter`: Builds Qdrant filter conditions from temporal queries
- **Key Functions**:
  - `generate_temporal_metadata()`: Creates 10-field temporal structure
  - `parse_temporal_query()`: Parses natural language time queries
  - `build_temporal_conditions()`: Converts to Qdrant filters
- **Supported Queries**: "today", "yesterday", "weekends", "q1-q4", "morning/afternoon/evening", day names
- **Temporal Fields**: day, hour, year, month, minute, quarter, is_weekend, day_of_week, day_of_year, week_of_year

#### `src/shared/duplicate_detector.py`
- **Purpose**: Comprehensive duplicate detection and handling system  
- **Key Classes**:
  - `DuplicateDetector`: Semantic similarity-based duplicate detection
  - `DuplicateHandler`: Multiple handling strategies for detected duplicates
- **Key Functions**:
  - `check_for_duplicates()`: Main duplicate detection with 0.95 threshold
  - `handle_duplicate()`: Support for skip, merge, or add actions
- **Important Features**:
  - Configurable similarity thresholds
  - Metadata-enhanced duplicate detection
  - Multiple handling strategies
  - Detailed similarity scoring

#### `src/search/enhanced_search_engine.py`
- **Purpose**: Comprehensive search engine with all advanced capabilities
- **Key Class**: `EnhancedSearchEngine`
- **Key Functions**:
  - `search_memories()`: Master search function with all filters
  - `temporal_search()`: Pure temporal and hybrid temporal+semantic search
  - `tag_search()`: Tag-based filtering with AND/OR logic
  - `people_search()`: People-mentioned filtering
  - `topic_search()`: Topic category filtering
- **Advanced Features**:
  - Comprehensive filter building and combination
  - Consistent result formatting
  - Score-based relevance filtering
  - Hybrid search capabilities

#### `constants.py` (Enhanced)
- **Purpose**: Comprehensive configuration management for all new features
- **Enhanced Classes**:
  - `SearchConstants`: Enhanced search limits and thresholds
  - `DuplicateConstants`: Duplicate detection configuration
  - `TemporalConstants`: Time period definitions and mappings
  - `MetadataConstants`: Field names and structures
  - `SearchFilters`: Filter types and operators
- **Important Features**:
  - No magic numbers throughout codebase
  - Comprehensive temporal period mappings
  - Quarter definitions and weekday lists
  - Filter operation definitions

### Enhanced Memory Payload Structure

```json
{
  "memory": "User's memory content",
  "timestamp": "2025-07-19T17:42:00Z",
  "temporal": {
    "day": 19, "hour": 17, "year": 2025, "month": 7, "minute": 42,
    "quarter": 3, "is_weekend": true, "day_of_week": "saturday",
    "day_of_year": 200, "week_of_year": 29
  },
  "tags": ["work", "meeting", "project"],
  "people_mentioned": ["John", "Sarah", "Mike"],
  "topic_category": "work"
}
```

## MCP Tool Capabilities

### Enhanced Memory Addition
- **add_memory_with_metadata**: Rich metadata addition with duplicate detection
- **Parameters**: memory_content, tags, people_mentioned, topic_category, check_duplicates
- **Features**: Automatic temporal data, duplicate prevention, formatted responses

### Advanced Search Capabilities
- **search_memories_enhanced**: Master search with all filtering options
- **temporal_search**: Natural language time-based search
- **search_by_tags**: Tag filtering with AND/OR logic
- **search_by_people**: People-mentioned filtering  
- **search_by_topic**: Topic category filtering

### Supported Natural Language Queries
- **Time Periods**: "today", "yesterday", "this_week", "last_week"
- **Day Types**: "weekends", "weekdays"  
- **Quarters**: "q1", "q2", "q3", "q4"
- **Time of Day**: "morning", "afternoon", "evening"
- **Specific Days**: "monday", "tuesday", etc.

## Clean Code Implementation

### Design Principles Applied
1. **Single Responsibility Principle**: Each class has one clear purpose
2. **Open/Closed Principle**: Extensible without modification
3. **Interface Segregation**: Clean, focused interfaces
4. **Dependency Injection**: Configurable components
5. **Factory Pattern**: Search engine creation
6. **Strategy Pattern**: Multiple duplicate handling strategies

### Error Handling Strategy
- Comprehensive try-catch blocks at all levels
- Input validation at function entry points
- Graceful degradation for parsing failures
- Detailed logging for debugging
- User-friendly error messages with emojis

### Code Organization
- Clear module separation by functionality
- Consistent naming conventions throughout
- Comprehensive type hints and docstrings
- No magic numbers or hardcoded values
- Clean import organization

## Configuration & Dependencies
- **Embedding Model**: `mxbai-embed-large` (1024 dimensions)
- **Vector Database**: Qdrant on localhost:6333
- **Collection**: `test_collection_mcps`
- **Similarity Threshold**: 0.95 for duplicates, 0.7 for search
- **Default Limits**: 5 search results, max 20
- **Dependencies**: qdrant-client, ollama, mcp, typing

## Usage Examples

### Adding Enhanced Memories
```python
# Add memory with rich metadata
add_memory_with_metadata(
    memory_content="Discussed vector database optimization with the team",
    tags="work,database,optimization",
    people_mentioned="John,Sarah",
    topic_category="technology",
    check_duplicates=True
)
```

### Advanced Searching
```python
# Comprehensive search
search_memories_enhanced(
    query="database optimization",
    tags="work,technology",
    people_mentioned="John",
    temporal_filter="this_week",
    limit=5
)

# Temporal search
temporal_search(
    temporal_query="yesterday",
    semantic_query="meetings"
)
```

## Testing Status
- [✅] Core functionality implemented and tested
- [✅] All MCP tools functional
- [✅] Backward compatibility maintained
- [⏳] Comprehensive integration testing pending
- [⏳] Performance testing with large datasets pending

## Future Enhancement Opportunities
- **Batch Operations**: Multiple memory operations in single requests
- **Advanced Analytics**: Memory pattern analysis and insights
- **Automatic Tagging**: AI-powered tag suggestion
- **Export/Import**: Memory backup and restoration
- **Advanced Visualization**: Memory relationship mapping

## Recent Major Changes
- **Complete Architecture Overhaul**: Added 5 new modules with clean separation
- **Rich Metadata System**: 10+ temporal fields plus tags/people/topics
- **Duplicate Prevention**: Sophisticated similarity-based detection
- **Natural Language Temporal Queries**: Human-friendly time-based search
- **Comprehensive Search Engine**: 6 different search methods
- **Enhanced MCP Tools**: 8 total tools (2 legacy + 6 enhanced)
- **Clean Code Refactoring**: Uncle Bob principles throughout
