import path from 'path';
import resolve from '@rollup/plugin-node-resolve';
import commonjs from '@rollup/plugin-commonjs';
import { terser } from 'rollup-plugin-terser';
import postcss from 'rollup-plugin-postcss';
import json from '@rollup/plugin-json';
import copy from 'rollup-plugin-copy';

export default {
  input: 'src/index.js',
  output: {
    file: 'dist/chatbot.min.js',
    format: 'iife',
    name: 'ChatbotPlugin',
    sourcemap: false,
  },
  plugins: [
    json(),
    resolve(),
    commonjs(),
    postcss({
      extract: path.resolve('dist/chatbot.css'),
      minimize: true,
    }),


    copy({
      targets: [
        {
          src: 'src/assets/**/*',
          dest: 'dist/assets'
        }
      ]
    }),

    terser(),
  ],
};
