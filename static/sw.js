/**
 * Service Worker - 提供離線功能和快取策略
 */

console.log('Service Worker loaded');

const CACHE_NAME = 'ai-chat-v1.0.0';

self.addEventListener('install', function(event) {
    console.log('Service Worker installing');
    self.skipWaiting();
});

self.addEventListener('activate', function(event) {
    console.log('Service Worker activating');
});