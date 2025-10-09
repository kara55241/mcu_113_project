import { createApp } from 'vue'
import './assets/styles/main.css'
import App from './App.vue'
import router from './router'

// 導入 Vue Flow 樣式
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'

const app = createApp(App)

app.use(router)

app.mount('#app')
