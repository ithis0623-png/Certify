<?php

use App\Http\Controllers\CertificateController;
use Illuminate\Support\Facades\Route;

Route::get('/certificates', [CertificateController::class, 'index']);
Route::post('/certificates', [CertificateController::class, 'store']);
Route::get('/certificates/{publicId}', [CertificateController::class, 'show']);
Route::post('/certificates/{publicId}/revoke', [CertificateController::class, 'revoke']);
