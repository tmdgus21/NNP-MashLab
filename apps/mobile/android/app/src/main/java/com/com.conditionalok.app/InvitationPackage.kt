package com.conditionalok.app

import android.content.Intent
import android.content.ActivityNotFoundException
import com.facebook.react.ReactPackage
import com.facebook.react.bridge.NativeModule
import com.facebook.react.bridge.Promise
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.bridge.ReactContextBaseJavaModule
import com.facebook.react.bridge.ReactMethod
import com.facebook.react.uimanager.ViewManager

class InvitationModule(context: ReactApplicationContext) : ReactContextBaseJavaModule(context) {
  override fun getName() = "ConditionalOKInvitation"
  @ReactMethod
  fun newRequestKey(promise: Promise) { promise.resolve(java.util.UUID.randomUUID().toString()) }
  @ReactMethod
  fun shareKakao(text: String, promise: Promise) {
    try {
      val intent = Intent(Intent.ACTION_SEND).apply {
        type = "text/plain"
        putExtra(Intent.EXTRA_TEXT, text)
        setPackage("com.kakao.talk")
        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
      }
      reactApplicationContext.startActivity(intent)
      // Only the share screen was opened; never claim the message was sent.
      promise.resolve(null)
    } catch (error: ActivityNotFoundException) {
      promise.reject("KAKAO_NOT_INSTALLED", "카카오톡이 설치되어 있지 않습니다. 일반 공유를 이용해 주세요.")
    } catch (error: Exception) {
      promise.reject("SHARE_FAILED", "카카오톡 공유 화면을 열지 못했습니다.", error)
    }
  }
}

class InvitationPackage : ReactPackage {
  override fun createNativeModules(context: ReactApplicationContext): List<NativeModule> = listOf(InvitationModule(context))
  override fun createViewManagers(context: ReactApplicationContext): List<ViewManager<*, *>> = emptyList()
}
