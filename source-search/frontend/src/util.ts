export class WindowedAverager {
    windowSize: number;
    values: number[];

    constructor(windowSize: number) {
        this.windowSize = windowSize;
        this.values = [];
    }

    add(value: number) {
        this.values.push(value);
        if (this.values.length > this.windowSize) {
            this.values.shift();
        }
    }

    average() {
        if (this.values.length === 0) {
            return 0;
        }
        return this.values.reduce((a, b) => a + b) / this.values.length;
    }
}
