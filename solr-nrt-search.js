// SolrNRTSearch.js
const solr = require('solrjs');
const config = require('./config');

class SolrNRTSearch {
    constructor(options = {}) {
        this.mainCore = options.mainCore || 'main_core';
        this.realtimeCore = options.realtimeCore || 'realtime_core';
        this.commitWithin = options.commitWithin || 1000; // ms
        this.softCommitWithin = options.softCommitWithin || 500; // ms
        
        // Initialize Solr clients for both cores
        this.mainClient = new solr.createClient({
            host: config.solrHost,
            port: config.solrPort,
            core: this.mainCore
        });
        
        this.realtimeClient = new solr.createClient({
            host: config.solrHost,
            port: config.solrPort,
            core: this.realtimeCore
        });
    }

    async search(query, options = {}) {
        try {
            // Search in both cores
            const [mainResults, realtimeResults] = await Promise.all([
                this.searchMainCore(query, options),
                this.searchRealtimeCore(query, options)
            ]);

            // Merge and deduplicate results
            return this.mergeResults(mainResults, realtimeResults);
        } catch (error) {
            console.error('Search error:', error);
            throw error;
        }
    }

    async searchMainCore(query, options) {
        const queryParams = {
            q: query,
            start: options.start || 0,
            rows: options.rows || 10,
            sort: options.sort || 'score desc',
            fl: options.fields || '*',
            fq: options.filters || []
        };

        return this.mainClient.search(queryParams);
    }

    async searchRealtimeCore(query, options) {
        const queryParams = {
            q: query,
            start: options.start || 0,
            rows: options.rows || 10,
            sort: options.sort || 'score desc',
            fl: options.fields || '*',
            fq: options.filters || []
        };

        return this.realtimeClient.search(queryParams);
    }

    mergeResults(mainResults, realtimeResults) {
        // Create a Map to store unique documents by ID
        const mergedDocs = new Map();

        // Add realtime results first (they take precedence)
        realtimeResults.response.docs.forEach(doc => {
            mergedDocs.set(doc.id, doc);
        });

        // Add main core results if not already present
        mainResults.response.docs.forEach(doc => {
            if (!mergedDocs.has(doc.id)) {
                mergedDocs.set(doc.id, doc);
            }
        });

        return {
            response: {
                numFound: mergedDocs.size,
                docs: Array.from(mergedDocs.values())
            }
        };
    }

    async addDocument(document, options = {}) {
        try {
            // Add to realtime core with soft commit
            await this.realtimeClient.add(document, {
                commitWithin: this.commitWithin,
                softCommit: true,
                overwrite: true
            });

            // Schedule document for main core indexing if needed
            if (options.addToMainCore) {
                await this.scheduleMainCoreUpdate(document);
            }
        } catch (error) {
            console.error('Error adding document:', error);
            throw error;
        }
    }

    async scheduleMainCoreUpdate(document) {
        // Implementation for scheduling updates to main core
        // This could involve adding to a queue or other mechanism
        try {
            await this.mainClient.add(document, {
                commitWithin: this.commitWithin * 2
            });
        } catch (error) {
            console.error('Error scheduling main core update:', error);
            throw error;
        }
    }

    async deleteDocument(id) {
        try {
            // Delete from both cores
            await Promise.all([
                this.mainClient.deleteByQuery(`id:${id}`),
                this.realtimeClient.deleteByQuery(`id:${id}`)
            ]);

            // Commit changes
            await this.commitChanges();
        } catch (error) {
            console.error('Error deleting document:', error);
            throw error;
        }
    }

    async commitChanges() {
        try {
            await Promise.all([
                this.mainClient.commit(),
                this.realtimeClient.softCommit()
            ]);
        } catch (error) {
            console.error('Error committing changes:', error);
            throw error;
        }
    }
}

module.exports = SolrNRTSearch;
