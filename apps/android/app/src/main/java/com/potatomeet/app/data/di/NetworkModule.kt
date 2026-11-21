package com.potatomeet.app.data.di

import com.potatomeet.app.BuildConfig
import com.potatomeet.app.core.TokenStore
import com.potatomeet.app.data.remote.PotatoApi
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {
    @Provides
    @Singleton
    fun json(): Json =
        Json {
            ignoreUnknownKeys = true
            isLenient = true
            explicitNulls = false
        }

    @Provides
    @Singleton
    fun okHttp(tokenStore: TokenStore): OkHttpClient {
        val logging =
            HttpLoggingInterceptor().apply {
                level = HttpLoggingInterceptor.Level.BASIC
            }
        return OkHttpClient.Builder()
            .addInterceptor { chain ->
                val token = runBlocking { tokenStore.token() }
                val req =
                    if (token.isNullOrBlank()) {
                        chain.request()
                    } else {
                        chain.request().newBuilder()
                            .header("Authorization", "Bearer $token")
                            .build()
                    }
                chain.proceed(req)
            }
            .addInterceptor(logging)
            // SSE long-lived reads; REST calls complete well under this.
            .readTimeout(0, java.util.concurrent.TimeUnit.MILLISECONDS)
            .build()
    }

    @Provides
    @Singleton
    fun retrofit(
        client: OkHttpClient,
        json: Json,
    ): Retrofit {
        val base = BuildConfig.API_BASE_URL.trimEnd('/') + "/"
        return Retrofit.Builder()
            .baseUrl(base)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
    }

    @Provides
    @Singleton
    fun potatoApi(retrofit: Retrofit): PotatoApi = retrofit.create(PotatoApi::class.java)
}
