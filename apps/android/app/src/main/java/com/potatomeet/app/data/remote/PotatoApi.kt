package com.potatomeet.app.data.remote

import com.potatomeet.app.data.remote.dto.AuthChallengeRequest
import com.potatomeet.app.data.remote.dto.AuthChallengeResponse
import com.potatomeet.app.data.remote.dto.AuthTokenResponse
import com.potatomeet.app.data.remote.dto.AuthVerifyRequest
import com.potatomeet.app.data.remote.dto.CandidatesResponse
import com.potatomeet.app.data.remote.dto.CollectionResponse
import com.potatomeet.app.data.remote.dto.CreateMeetingRequest
import com.potatomeet.app.data.remote.dto.JoinMeetingRequest
import com.potatomeet.app.data.remote.dto.LoginRequest
import com.potatomeet.app.data.remote.dto.MeResponse
import com.potatomeet.app.data.remote.dto.MeetingDto
import com.potatomeet.app.data.remote.dto.MeetingListResponse
import com.potatomeet.app.data.remote.dto.NicknamePatchRequest
import com.potatomeet.app.data.remote.dto.RegisterRequest
import com.potatomeet.app.data.remote.dto.ResultResponse
import com.potatomeet.app.data.remote.dto.RevisionRequest
import com.potatomeet.app.data.remote.dto.ServerTimeResponse
import com.potatomeet.app.data.remote.dto.SubmitResponseRequest
import com.potatomeet.app.data.remote.dto.VoteRequest
import kotlinx.serialization.json.JsonObject
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.HTTP
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path

/** Paths relative to BuildConfig.API_BASE_URL (…/v1). */
interface PotatoApi {
    @POST("auth/register")
    suspend fun register(
        @Body body: RegisterRequest,
    ): AuthChallengeResponse

    @POST("auth/register/resend")
    suspend fun registerResend(
        @Body body: AuthChallengeRequest,
    ): AuthChallengeResponse

    @POST("auth/register/verify")
    suspend fun registerVerify(
        @Body body: AuthVerifyRequest,
    ): AuthTokenResponse

    @POST("auth/login")
    suspend fun login(
        @Body body: LoginRequest,
    ): AuthChallengeResponse

    @POST("auth/login/resend")
    suspend fun loginResend(
        @Body body: AuthChallengeRequest,
    ): AuthChallengeResponse

    @POST("auth/login/verify")
    suspend fun loginVerify(
        @Body body: AuthVerifyRequest,
    ): AuthTokenResponse

    @GET("auth/me")
    suspend fun me(): MeResponse

    @PATCH("auth/me/nickname")
    suspend fun patchNickname(
        @Body body: NicknamePatchRequest,
    ): MeResponse

    @POST("auth/logout")
    suspend fun logout()

    @GET("time")
    suspend fun serverTime(): ServerTimeResponse

    @GET("meetings")
    suspend fun listMeetings(): MeetingListResponse

    @POST("meetings")
    suspend fun createMeeting(
        @Body body: CreateMeetingRequest,
    ): MeetingDto

    @POST("meetings/join")
    suspend fun joinMeeting(
        @Body body: JoinMeetingRequest,
    ): MeetingDto

    @GET("meetings/{id}")
    suspend fun getMeeting(
        @Path("id") id: String,
    ): MeetingDto

    @HTTP(method = "DELETE", path = "meetings/{id}", hasBody = true)
    suspend fun deleteMeeting(
        @Path("id") id: String,
        @Body body: RevisionRequest,
    ): JsonObject

    @GET("meetings/{id}/collection")
    suspend fun getCollection(
        @Path("id") id: String,
    ): CollectionResponse

    @PUT("meetings/{id}/collections/{collectionId}/response")
    suspend fun submitResponse(
        @Path("id") id: String,
        @Path("collectionId") collectionId: String,
        @Body body: SubmitResponseRequest,
    ): CollectionResponse

    @GET("meetings/{id}/candidates")
    suspend fun getCandidates(
        @Path("id") id: String,
    ): CandidatesResponse

    @PUT("meetings/{id}/votes/me")
    suspend fun submitVotes(
        @Path("id") id: String,
        @Body body: VoteRequest,
    ): CandidatesResponse

    @GET("meetings/{id}/result")
    suspend fun getResult(
        @Path("id") id: String,
    ): ResultResponse
}
