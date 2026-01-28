import { useEffect, useRef } from 'react';
import * as PIXI from 'pixi.js';
import { Live2DModel } from 'pixi-live2d-display';

// Expose PIXI to window for the plugin
window.PIXI = PIXI;
Live2DModel.registerTicker(PIXI.Ticker);

const Live2DViewer = ({ emotion, isTalking }) => {
    const canvasRef = useRef(null);
    const appRef = useRef(null);
    const modelRef = useRef(null);

    useEffect(() => {
        if (modelRef.current && isTalking) {
            // 收到正在播放语音的信号时，尝试驱动口型
            // 1. 如果有 motions 可以播放 Speak
            // 2. 如果没有动作，简单地开启 lipSync (需要音量，这里暂模拟)
            try {
                if (modelRef.current.internalModel && modelRef.current.internalModel.motionManager) {
                    modelRef.current.motion('Speak'); 
                }
            } catch (e) { console.log(e); }
        }
    }, [isTalking]);

    useEffect(() => {
        if (modelRef.current && emotion) {
            console.log("Playing expression from prop:", emotion);
            try {
                // 将 emotion 代码映射到模型支持的表情名 (首字母大写等)
                const expressionMap = {
                    'happy': 'Happy',
                    'sad': 'Sad',
                    'angry': 'Angry',
                    'surprised': 'Surprised',
                    'wink': 'Wink',
                    'blush': 'Blush'
                };
                const expName = expressionMap[emotion.toLowerCase()] || emotion;
                if (modelRef.current.expression) {
                    modelRef.current.expression(expName);
                }
            } catch (err) {
                console.error("Failed to play expression:", err);
            }
        }
    }, [emotion]);

    useEffect(() => {
        if (!canvasRef.current) return;
        if (appRef.current) return;

        const init = async () => {
            try {
                const app = new PIXI.Application({
                    view: canvasRef.current,
                    width: 1200,
                    height: 1800,
                    transparent: true,
                    autoStart: true,
                });
                appRef.current = app;

                const model = await Live2DModel.from('/models/LSS/LSS.model3.json', {
                    autoInteract: false
                });

                if (!appRef.current || appRef.current !== app) {
                    model.destroy();
                    return;
                }

                modelRef.current = model;
                app.stage.addChild(model);

                try {
                    model.anchor.set(0.5);
                    model.x = app.renderer.width / 2;
                    model.y = app.renderer.height / 2;
                } catch (e) {
                    model.x = app.renderer.width / 2;
                    model.y = app.renderer.height / 2;
                }

                const scaleX = app.renderer.width / model.width;
                const scaleY = app.renderer.height / model.height;
                model.scale.set(Math.min(scaleX, scaleY) * 1.0);

                console.log("Live2D Model Loaded via pixi-live2d-display");
                console.log("Model Size: ", model.width, model.height);
                console.log("Model Pos: ", model.x, model.y);
                console.log("Model Scale: ", model.scale.x);

            } catch (error) {
                console.error("Failed to load Live2D model:", error);
            }
        };

        init();
        return () => {
            if (appRef.current) {
                appRef.current.destroy(false, { children: true });
                appRef.current = null;
                modelRef.current = null;
            }
        };
    }, []);

    useEffect(() => {
        // 移除了随机表情切换，现在由外部 emotion prop 驱动
    }, []);

    return (
        <canvas id="live2d-canvas" ref={canvasRef} style={{ position: 'fixed', bottom: 0, right: 0, zIndex: 1, pointerEvents: 'none' }} />
    );
};

export default Live2DViewer;
