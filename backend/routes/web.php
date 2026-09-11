<?php

use App\Http\Controllers\CertificateEditorController;
use Illuminate\Support\Facades\Route;

Route::get('/', fn () => response(str_replace('__CSRF_TOKEN__', csrf_token(), file_get_contents(base_path('../index.html'))))->header('Cache-Control', 'no-store'))->name('dashboard');
Route::get('/styles.css', fn () => response()->file(base_path('../styles.css'), ['Content-Type' => 'text/css; charset=UTF-8']));
Route::get('/app.js', fn () => response()->file(base_path('../app.js'), ['Content-Type' => 'application/javascript; charset=UTF-8']));
Route::get('/editor/template', [CertificateEditorController::class, 'template'])->name('editor.template');
Route::get('/editor/background', [CertificateEditorController::class, 'background'])->name('editor.background');
Route::post('/editor/preview', [CertificateEditorController::class, 'preview'])->middleware('throttle:180,1')->name('editor.preview');
Route::post('/editor/export', [CertificateEditorController::class, 'export'])->middleware('throttle:20,1')->name('editor.export');
Route::get('/templates/hof-certificate', fn () => response()->file(
    base_path('../HOF_Certificate_Blank.ai'),
    ['Content-Type' => 'application/pdf', 'Content-Disposition' => 'inline; filename="HOF_Certificate_Blank.pdf"']
));
