type AMapWindow = Window & {
  AMap?: any;
  _AMapSecurityConfig?: {
    securityJsCode?: string;
  };
};

const AMAP_JS_KEY = (import.meta.env.VITE_AMAP_JS_KEY || '').trim();
const AMAP_SECURITY_CODE = (import.meta.env.VITE_AMAP_SECURITY_CODE || '').trim();
const AMAP_SCRIPT_ID = 'travel-assistant-amap-script';

let loadPromise: Promise<any> | null = null;

export function getAmapConfigError() {
  if (!AMAP_JS_KEY) {
    return '未配置 VITE_AMAP_JS_KEY，无法显示高德地图。';
  }

  return '';
}

export async function loadAmap() {
  const configError = getAmapConfigError();
  if (configError) {
    throw new Error(configError);
  }

  const amapWindow = window as AMapWindow;
  if (amapWindow.AMap) {
    return amapWindow.AMap;
  }

  if (!loadPromise) {
    loadPromise = new Promise((resolve, reject) => {
      if (AMAP_SECURITY_CODE) {
        amapWindow._AMapSecurityConfig = {
          securityJsCode: AMAP_SECURITY_CODE,
        };
      }

      const existingScript = document.getElementById(AMAP_SCRIPT_ID) as HTMLScriptElement | null;
      if (existingScript) {
        existingScript.addEventListener('load', () => resolve(amapWindow.AMap));
        existingScript.addEventListener('error', () => reject(new Error('高德地图脚本加载失败。')));
        return;
      }

      const script = document.createElement('script');
      script.id = AMAP_SCRIPT_ID;
      script.async = true;
      script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(AMAP_JS_KEY)}&plugin=AMap.Scale,AMap.ToolBar`;
      script.onload = () => {
        if (amapWindow.AMap) {
          resolve(amapWindow.AMap);
          return;
        }

        reject(new Error('高德地图脚本已加载，但 AMap 对象不可用。'));
      };
      script.onerror = () => reject(new Error('高德地图脚本加载失败。'));
      document.head.appendChild(script);
    }).catch((error) => {
      loadPromise = null;
      throw error;
    });
  }

  return loadPromise;
}
