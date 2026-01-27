import { useEffect, useRef } from 'react';
import * as PIXI from 'pixi.js';
import { Live2DModel } from 'pixi-live2d-display';

// Expose PIXI to window for the plugin
window.PIXI = PIXI;
Live2DModel.registerTicker(PIXI.Ticker);

const Live2DViewer = () => {
    const canvasRef = useRef(null);
    const appRef = useRef(null);
    const modelRef = useRef(null);

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
        const playExpression = () => {
            if (!modelRef.current) return;

            const expressions = [
                "Happy", "Normal"
            ];

            const randomExpression = expressions[Math.floor(Math.random() * expressions.length)];
            console.log("Switching expression to:", randomExpression);
            if (modelRef.current.expression) {
                modelRef.current.expression(randomExpression);
            } else {
                console.warn("model.expression method missing");
            }
        };

        const intervalId = setInterval(playExpression, 4000);

        return () => {
            clearInterval(intervalId);
        };
    }, []);

    return (
        <canvas id="live2d-canvas" ref={canvasRef} style={{ position: 'fixed', bottom: 0, right: 0, zIndex: 1, pointerEvents: 'none' }} />
    );
};

export default Live2DViewer;
