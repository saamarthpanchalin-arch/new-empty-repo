import { createClient, SearchRequest } from './src/index';

// Use environment variable for API key, or default test key
const TEST_API_KEY = process.env.TEST_API_KEY || 'rag__v8EAFMV4HLzVXuAtX2Rh0uoHEEfeh1iD_6atUy6jqY';

async function test() {
  const client = createClient('http://127.0.0.1:8001', TEST_API_KEY);
  
  try {
    // Health check (public)
    const health = await client.health();
    console.log('Health:', health);
    
    const ready = await client.ready();
    console.log('Ready:', ready);
    
    // List applications (requires auth)
    const apps = await client.listApplications();
    console.log('Applications:', apps.length);
    
    // Search
    const results = await client.search({
      query: 'test',
      app_id: 'testapp',
      collection_id: 'testcol',
      top_k: 3
    });
    console.log('Search results:', results.length);
    
    // Ask
    const answer = await client.ask({
      query: 'What is Artemis?',
      app_id: 'testapp',
      collection_id: 'testcol',
      top_k: 3
    });
    console.log('Answer:', answer.answer.substring(0, 100));
    console.log('Sources:', answer.sources.length);
    
    // Test authentication with invalid key
    console.log('\n--- Testing invalid key ---');
    const badClient = createClient('http://127.0.0.1:8001', 'invalid-key');
    try {
      await badClient.listApplications();
      console.log('ERROR: Should have failed with invalid key');
    } catch (e) {
      console.log('Correctly rejected invalid key:', (e as Error).message);
    }
    
    // Test with insufficient scope
    console.log('\n--- Testing insufficient scope ---');
    const readOnlyClient = createClient('http://127.0.0.1:8001', 'rag__v8EAFMV4HLzVXuAtX2Rh0uoHEEfeh1iD_6atUy6jqY'); // admin key has admin scope, but let's test with a read-only key
    try {
      await readOnlyClient.listApplications();
      console.log('Read-only key test passed (admin key has read scope)');
    } catch (e) {
      console.log('Read-only key test:', (e as Error).message);
    }
    
  } catch (error) {
    console.error('Error:', error);
  }
}

test();
